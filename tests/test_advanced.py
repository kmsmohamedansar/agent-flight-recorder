import json
import tempfile
import unittest
from pathlib import Path

from flightrecorder import FlightRecorder
from flightrecorder import __version__
from flightrecorder.compare import compare_runs
from flightrecorder.demo_agent import run_demo
from flightrecorder.export import to_json, to_otlp
from flightrecorder.investigate import investigate
from flightrecorder.replay import RecordedToolError, ReplayMismatch, ReplayTape
from flightrecorder.store import SCHEMA_VERSION, SQLiteStore
from flightrecorder.web import HTML, api_response


class AdvancedFlightRecorderTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.db = str(self.root / "test.sqlite")
        self.store = SQLiteStore(self.db)

    def tearDown(self):
        self.tempdir.cleanup()

    def _record(self, run_id, output, status="ok"):
        recorder = FlightRecorder(self.db)
        with recorder.run("comparison", run_id=run_id) as run:
            run.record("tool", input={"value": 1}, output=output, status=status)

    def test_schema_version_and_failed_step_status(self):
        self._record("run-failed", {"ok": False}, status="failed")
        with self.store.connect() as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
        self.assertEqual(version, SCHEMA_VERSION)
        self.assertEqual(self.store.get_run("run-failed")["status"], "failed")

    def test_retention_prune_is_dry_run_by_default(self):
        self._record("run-old", {"old": True})
        with self.store.connect() as connection:
            connection.execute(
                "UPDATE runs SET started_at = '2000-01-01T00:00:00+00:00' "
                "WHERE id = 'run-old'"
            )
        candidates = self.store.prune_runs(
            "2020-01-01T00:00:00+00:00", keep_latest=0
        )
        self.assertEqual(candidates, ["run-old"])
        self.assertIsNotNone(self.store.get_run("run-old"))
        self.store.prune_runs(
            "2020-01-01T00:00:00+00:00", keep_latest=0, dry_run=False
        )
        self.assertIsNone(self.store.get_run("run-old"))

    def test_retention_keep_latest_applies_to_recent_runs(self):
        self._record("run-one", {"value": 1})
        self._record("run-two", {"value": 2})
        self._record("run-three", {"value": 3})
        candidates = self.store.prune_runs(
            "2000-01-01T00:00:00+00:00", keep_latest=1
        )
        self.assertEqual(len(candidates), 2)
        self.assertNotIn("run-three", candidates)

    def test_compare_finds_first_output_divergence(self):
        self._record("run-left", {"answer": 1})
        self._record("run-right", {"answer": 2})
        result = compare_runs(
            self.store.get_run("run-left"), self.store.get_run("run-right")
        )
        self.assertEqual(result["first_divergence"]["position"], 1)
        self.assertIn("output_changed", result["first_divergence"]["reasons"])

    def test_json_and_otlp_exports(self):
        self._record("run-export", {"answer": 42})
        run = self.store.get_run("run-export")
        self.assertEqual(to_json(run)["schema_version"], 1)
        span = to_otlp(run)["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
        self.assertEqual(span["name"], "tool")
        self.assertEqual(len(span["traceId"]), 32)
        scope = to_otlp(run)["resourceSpans"][0]["scopeSpans"][0]["scope"]
        self.assertEqual(scope["version"], __version__)

    def test_replay_tape_returns_results_and_replays_errors(self):
        recorder = FlightRecorder(self.db)
        with recorder.run("replay", run_id="run-replay") as run:
            run.record("first", output={"answer": 42})
            run.record("second", status="failed", error="recorded failure")
        tape = ReplayTape(self.store.get_run("run-replay"))
        self.assertEqual(tape.next("first"), {"answer": 42})
        with self.assertRaises(RecordedToolError):
            tape.next("second")
        with self.assertRaises(ReplayMismatch):
            tape.next()

    def test_real_demo_uses_files_subprocess_and_localizes_failure(self):
        run_id = run_demo(FlightRecorder(self.db), self.root / "workspace")
        run = self.store.get_run(run_id)
        self.assertEqual(run["status"], "failed")
        self.assertEqual([step["kind"] for step in run["steps"]], ["file_read", "file_write", "test"])
        result = investigate(run)
        self.assertEqual(result["suspect"]["name"], "Apply agent edit")
        self.assertTrue(result["change"]["path"].endswith("payment_service.py"))

    def test_local_web_api_routes_runs_and_investigation(self):
        self._record("run-web", {"ok": True})
        status, runs = api_response(self.store, "/api/runs")
        detail_status, run = api_response(self.store, "/api/runs/run-web")
        investigation_status, result = api_response(
            self.store, "/api/investigate/run-web"
        )
        self.assertEqual((status, detail_status, investigation_status), (200, 200, 200))
        self.assertEqual(runs[0]["id"], "run-web")
        self.assertEqual(run["steps"][0]["name"], "tool")
        self.assertIsNone(result["failure"])
        self.assertIn("Agent Flight Recorder", HTML)


if __name__ == "__main__":
    unittest.main()

