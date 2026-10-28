import asyncio
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flightrecorder import FlightRecorder
from flightrecorder.investigate import investigate
from flightrecorder.store import SQLiteStore


class FlightRecorderTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tempdir.name) / "test.sqlite")

    def tearDown(self):
        self.tempdir.cleanup()

    def test_records_run_and_steps(self):
        recorder = FlightRecorder(self.db)
        with recorder.run("example", run_id="run-test") as run:
            run.record("read", kind="file_read", output={"ok": True})

        result = SQLiteStore(self.db).get_run("run-test")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["steps"][0]["output"], {"ok": True})

    def test_context_step_records_failure(self):
        recorder = FlightRecorder(self.db)
        with self.assertRaisesRegex(ValueError, "boom"):
            with recorder.run("example", run_id="run-fail") as run:
                with run.step("broken tool"):
                    raise ValueError("boom")

        result = SQLiteStore(self.db).get_run("run-fail")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["steps"][0]["status"], "failed")
        self.assertIn("boom", result["steps"][0]["error"])

    def test_investigation_prefers_implicated_path(self):
        recorder = FlightRecorder(self.db)
        with recorder.run("example", run_id="run-investigate") as run:
            with run.step("edit target", kind="file_write") as step:
                step.add_change("target.py", "safe = True", "safe = False")
            with run.step("edit other", kind="file_write") as step:
                step.add_change("other.py", "a = 1", "a = 2")
            run.record(
                "test",
                kind="test",
                status="failed",
                error="assertion failed",
                metadata={"implicated_paths": ["target.py"]},
            )
            run.finish("failed")

        result = investigate(SQLiteStore(self.db).get_run("run-investigate"))
        self.assertEqual(result["suspect"]["name"], "edit target")
        self.assertEqual(result["change"]["path"], "target.py")

    def test_redacts_secrets_before_persistence(self):
        recorder = FlightRecorder(self.db)
        with recorder.run("secret", run_id="run-secret") as run:
            run.record(
                "request",
                input={"api_key": "sk-sensitive", "headers": {"Authorization": "Bearer abc123"}},
                output="password=hunter2",
            )

        raw_database = Path(self.db).read_bytes()
        self.assertNotIn(b"sk-sensitive", raw_database)
        self.assertNotIn(b"abc123", raw_database)
        self.assertNotIn(b"hunter2", raw_database)
        step = SQLiteStore(self.db).get_run("run-secret")["steps"][0]
        self.assertEqual(step["input"]["api_key"], "<redacted>")

    def test_redacts_common_secret_shapes_and_connection_passwords(self):
        recorder = FlightRecorder(self.db)
        with recorder.run("secret shapes", run_id="run-secret-shapes") as run:
            run.record(
                "request",
                input={
                    "tok": "sk-live-abcdef1234567890",
                    "GITHUB_TOKEN": "ghp_AAAAAAAAAAAAAAAA",
                    "AWS_SECRET_ACCESS_KEY": "wJalrXUtnFEMIEXAMPLE",
                    "url": "postgres://admin:s3cr3tpw@db.example/app",
                },
            )

        raw_database = Path(self.db).read_bytes()
        for secret in (
            b"sk-live-abcdef1234567890",
            b"ghp_AAAAAAAAAAAAAAAA",
            b"wJalrXUtnFEMIEXAMPLE",
            b"s3cr3tpw",
        ):
            self.assertNotIn(secret, raw_database)

    def test_database_is_owner_readable_and_writable_only(self):
        SQLiteStore(self.db)
        mode = stat.S_IMODE(Path(self.db).stat().st_mode)
        self.assertEqual(mode, 0o600)

    def test_git_context_is_opt_in_and_cannot_break_recording(self):
        with patch("flightrecorder.recorder.git_state") as git_state:
            recorder = FlightRecorder(self.db)
            with recorder.run("default", run_id="run-no-git"):
                pass
            git_state.assert_not_called()

        error = UnicodeDecodeError("utf-8", b"\xe9", 0, 1, "invalid")
        with patch("flightrecorder.recorder.git_state", side_effect=error):
            recorder = FlightRecorder(self.db, capture_git=True)
            with recorder.run("safe", run_id="run-git-safe") as run:
                run.record("step")
        self.assertEqual(SQLiteStore(self.db).get_run("run-git-safe")["status"], "ok")

    def test_non_utf8_git_diff_does_not_escape_run(self):
        root = Path(self.tempdir.name) / "repo"
        root.mkdir()
        subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
        (root / ".gitattributes").write_text("*.txt diff\n", encoding="utf-8")
        target = root / "legacy.txt"
        target.write_bytes(b"caf\xe9\n")
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(root), "commit", "-m", "fixture"],
            check=True,
            capture_output=True,
            env={
                "PATH": os.environ["PATH"],
                "GIT_AUTHOR_NAME": "Test",
                "GIT_AUTHOR_EMAIL": "test@example.com",
                "GIT_COMMITTER_NAME": "Test",
                "GIT_COMMITTER_EMAIL": "test@example.com",
            },
        )
        target.write_bytes(b"caf\xe9 changed\n")

        recorder = FlightRecorder(self.db, capture_git=True)
        with recorder.run(
            "legacy diff", run_id="run-legacy", metadata={"workspace": str(root)}
        ):
            pass

        run = SQLiteStore(self.db).get_run("run-legacy")
        self.assertEqual(run["status"], "ok")
        self.assertIn("legacy.txt", run["metadata"]["git_before"]["working_diff"])

    def test_wraps_sync_and_async_tools(self):
        recorder = FlightRecorder(self.db)
        with recorder.run("tools", run_id="run-tools") as run:
            add = run.wrap_tool(lambda left, right: left + right, name="add")

            async def double(value):
                return value * 2

            recorded_double = run.wrap_tool(double)
            self.assertEqual(add(2, 3), 5)
            self.assertEqual(asyncio.run(recorded_double(4)), 8)

        steps = SQLiteStore(self.db).get_run("run-tools")["steps"]
        self.assertEqual([step["output"] for step in steps], [5, 8])

    def test_wrapper_automatically_captures_file_changes(self):
        target = Path(self.tempdir.name) / "example.py"
        target.write_text("safe = True\n", encoding="utf-8")
        recorder = FlightRecorder(self.db)

        def modify():
            target.write_text("safe = False\n", encoding="utf-8")

        with recorder.run("edit", run_id="run-edit") as run:
            run.wrap_tool(modify, watch_paths=[str(target)])()

        step = SQLiteStore(self.db).get_run("run-edit")["steps"][0]
        change = step["metadata"]["changes"][0]
        self.assertEqual(change["before"], "safe = True\n")
        self.assertEqual(change["after"], "safe = False\n")


if __name__ == "__main__":
    unittest.main()

