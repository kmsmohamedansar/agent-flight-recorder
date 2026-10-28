import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from flightrecorder.benchmark import run_benchmark
from flightrecorder.mcp_server import FlightRecorderService


class MCPAndBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tempdir.name) / "mcp.sqlite")
        self.service = FlightRecorderService(self.db)

    def tearDown(self):
        self.service.close()
        self.tempdir.cleanup()

    def test_mcp_service_records_and_investigates_run(self):
        started = self.service.start_recording(
            "MCP run", run_id="run-mcp", metadata={"source": "test"}
        )
        self.assertEqual(started["status"], "running")
        self.service.record_step(
            "run-mcp",
            "edit target",
            kind="file_write",
            metadata={
                "changes": [
                    {"path": "target.py", "before": "safe=True", "after": "safe=False"}
                ]
            },
        )
        self.service.record_step(
            "run-mcp",
            "run test",
            kind="test",
            status="failed",
            error="target.py failed",
            metadata={"implicated_paths": ["target.py"]},
        )
        finished = self.service.finish_recording("run-mcp")

        self.assertEqual(finished["status"], "failed")
        self.assertEqual(self.service.list_runs()[0]["id"], "run-mcp")
        result = self.service.investigate_run("run-mcp")
        self.assertEqual(result["change"]["path"], "target.py")

    def test_mcp_service_validates_active_runs_and_export_format(self):
        with self.assertRaisesRegex(ValueError, "not active"):
            self.service.record_step("missing", "step")
        with self.assertRaisesRegex(ValueError, "not found"):
            self.service.export_run("missing")

    def test_benchmark_passes_all_reference_cases(self):
        result = run_benchmark()
        self.assertEqual(result["passed"], result["total"])
        self.assertEqual(result["accuracy"], 1.0)
        self.assertGreaterEqual(result["total"], 5)

@unittest.skipUnless(importlib.util.find_spec("mcp"), "optional MCP SDK not installed")
class MCPProtocolSmokeTests(unittest.IsolatedAsyncioTestCase):
    async def test_stdio_server_lists_and_calls_tools(self):
        from mcp import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client

        with tempfile.TemporaryDirectory() as tempdir:
            db = str(Path(tempdir) / "protocol.sqlite")
            params = StdioServerParameters(
                command=sys.executable,
                args=["-m", "flightrecorder.mcp_server", "--db", db],
            )
            async with stdio_client(params) as streams:
                async with ClientSession(*streams) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    names = {tool.name for tool in tools.tools}
                    self.assertIn("start_recording", names)
                    self.assertIn("investigate_run", names)
                    for name, arguments in [
                        ("start_recording", {"name": "smoke", "run_id": "run-smoke"}),
                        ("record_step", {"run_id": "run-smoke", "name": "step"}),
                        ("finish_recording", {"run_id": "run-smoke"}),
                        ("show_run", {"run_id": "run-smoke"}),
                    ]:
                        result = await session.call_tool(name, arguments)
                        self.assertFalse(result.is_error)


if __name__ == "__main__":
    unittest.main()
