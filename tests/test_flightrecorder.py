import asyncio
import tempfile
import unittest
from pathlib import Path

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

