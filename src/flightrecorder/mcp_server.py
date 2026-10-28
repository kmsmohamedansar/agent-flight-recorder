"""Optional Model Context Protocol server for agent integrations."""

from __future__ import annotations

import argparse
import functools
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Sequence

from . import __version__
from .compare import compare_runs
from .export import to_json, to_otlp
from .investigate import investigate
from .recorder import FlightRecorder, RunSession
from .store import SQLiteStore


class FlightRecorderService:
    """Protocol-independent operations exposed by the MCP adapter."""

    def __init__(self, db_path: str = ".flightrecorder.sqlite") -> None:
        self.db_path = db_path
        self.store = SQLiteStore(db_path)
        self.recorder = FlightRecorder(db_path)
        self.active: Dict[str, RunSession] = {}

    def list_runs(self, limit: int = 20) -> List[Dict[str, Any]]:
        """List recent agent runs, newest first."""
        return self.store.list_runs(max(1, min(limit, 200)))

    def show_run(self, run_id: Optional[str] = None) -> Dict[str, Any]:
        """Return a recorded run and its ordered timeline."""
        return self._load(run_id)

    def investigate_run(self, run_id: Optional[str] = None) -> Dict[str, Any]:
        """Find the most likely earlier change behind a recorded failure."""
        return investigate(self._load(run_id))

    def compare_recordings(
        self, left_run_id: str, right_run_id: str
    ) -> Dict[str, Any]:
        """Find the first meaningful divergence between two runs."""
        return compare_runs(self._load(left_run_id), self._load(right_run_id))

    def export_run(
        self, run_id: Optional[str] = None, format: str = "json"
    ) -> Dict[str, Any]:
        """Export a run as native JSON or OTLP-shaped JSON."""
        run = self._load(run_id)
        if format == "json":
            return to_json(run)
        if format == "otlp":
            return to_otlp(run)
        raise ValueError("format must be 'json' or 'otlp'")

    def start_recording(
        self,
        name: str,
        run_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        capture_git: bool = False,
    ) -> Dict[str, Any]:
        """Start a run; Git working-tree capture is explicit and off by default."""
        session = self.recorder.run(
            name, run_id=run_id, metadata=metadata, capture_git=capture_git
        )
        if session.id in self.active:
            raise ValueError("run is already active: %s" % session.id)
        session.__enter__()
        self.active[session.id] = session
        return {"run_id": session.id, "status": "running", "name": name}

    def record_step(
        self,
        run_id: str,
        name: str,
        kind: str = "tool",
        status: str = "ok",
        input: Any = None,
        output: Any = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        changes: Optional[List[Dict[str, Optional[str]]]] = None,
    ) -> Dict[str, Any]:
        """Append an action. For edits, send changes with path/before/after so investigation can rank them."""
        session = self._active(run_id)
        if status not in ("ok", "failed"):
            raise ValueError("status must be 'ok' or 'failed'")
        step_metadata = dict(metadata or {})
        if changes:
            step_metadata["changes"] = changes
        elif kind == "file_write" and step_metadata.get("implicated_paths"):
            step_metadata["changes"] = [
                {"path": path, "before": None, "after": None}
                for path in step_metadata["implicated_paths"]
            ]
        session.record(
            name,
            kind=kind,
            status=status,
            input=input,
            output=output,
            error=error,
            metadata=step_metadata,
        )
        run = self._load(run_id)
        return {
            "run_id": run_id,
            "sequence": run["steps"][-1]["sequence"],
            "status": status,
        }

    def finish_recording(self, run_id: str, status: str = "ok") -> Dict[str, Any]:
        """Finish an active run and persist its final status."""
        if status not in ("ok", "failed", "cancelled"):
            raise ValueError("status must be 'ok', 'failed', or 'cancelled'")
        session = self._active(run_id)
        session.finish(status)
        del self.active[run_id]
        run = self._load(run_id)
        return {"run_id": run_id, "status": run["status"]}

    def close(self) -> None:
        """Mark any abandoned in-process recordings as cancelled."""
        for run_id, session in list(self.active.items()):
            session.finish("cancelled")
            del self.active[run_id]

    def _active(self, run_id: str) -> RunSession:
        try:
            return self.active[run_id]
        except KeyError:
            raise ValueError("run is not active in this server: %s" % run_id)

    def _load(self, run_id: Optional[str]) -> Dict[str, Any]:
        run = self.store.get_run(run_id)
        if run is None:
            raise ValueError("recording not found: %s" % (run_id or "latest"))
        return run


def create_server(db_path: str = ".flightrecorder.sqlite") -> Any:
    """Build the optional MCP 2.x server without loading it in the core runtime."""
    try:
        from mcp.server.mcpserver import MCPServer
        from mcp.server.mcpserver.exceptions import ToolError
    except ImportError as exc:
        raise RuntimeError(
            "MCP support is optional. Install it with: "
            "python -m pip install 'flightrecorder-ai[mcp]'"
        ) from exc

    service = FlightRecorderService(db_path)

    @asynccontextmanager
    async def lifespan(_: Any) -> Any:
        try:
            yield {"service": service}
        finally:
            service.close()

    server = MCPServer(
        "flightrecorder",
        description="Record, inspect, compare, and investigate local AI agent runs.",
        version=__version__,
        lifespan=lifespan,
    )
    def visible_errors(function: Any) -> Any:
        @functools.wraps(function)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            try:
                return function(*args, **kwargs)
            except ValueError as exc:
                raise ToolError(str(exc)) from exc

        return wrapped

    server.tool()(visible_errors(service.list_runs))
    server.tool()(visible_errors(service.show_run))
    server.tool()(visible_errors(service.investigate_run))
    server.tool()(visible_errors(service.compare_recordings))
    server.tool()(visible_errors(service.export_run))
    server.tool()(visible_errors(service.start_recording))
    server.tool()(visible_errors(service.record_step))
    server.tool()(visible_errors(service.finish_recording))
    return server


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="flightrecorder-mcp")
    parser.add_argument("--db", default=".flightrecorder.sqlite")
    args = parser.parse_args(argv)
    try:
        server = create_server(args.db)
    except RuntimeError as exc:
        parser.error(str(exc))
    server.run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
