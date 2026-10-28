"""Command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from . import __version__
from .compare import compare_runs
from .benchmark import run_benchmark
from .demo_agent import run_demo as run_agent_demo
from .export import to_json, to_otlp
from .investigate import investigate
from .recorder import FlightRecorder
from .store import SQLiteStore


DEFAULT_DB = ".flightrecorder.sqlite"


def _load(store: SQLiteStore, run_id: Optional[str]) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        target = run_id or "latest run"
        raise SystemExit("No recording found for %s." % target)
    return run


def _demo(recorder: FlightRecorder) -> str:
    before = """def charge(order):
    if order.already_paid:
        raise DuplicatePayment(order.id)
    return gateway.charge(order)
"""
    after = """def charge(order):
    return gateway.charge(order)
"""
    preferred_id = "run-1042"
    run_id = (
        preferred_id
        if recorder.store.get_run(preferred_id) is None
        else "run-demo-" + uuid.uuid4().hex[:8]
    )
    with recorder.run("Payment bug fix", run_id=run_id) as run:
        run.record(
            "Read payment_service.py",
            kind="file_read",
            input={"path": "payment_service.py"},
            output={"bytes": len(before)},
        )
        with run.step(
            "Modified payment_service.py",
            kind="file_write",
            input={"path": "payment_service.py"},
        ) as step:
            step.add_change("payment_service.py", before, after)
            step.set_output({"written": True})
        run.record(
            "Updated database query",
            kind="database",
            input={"operation": "share transaction"},
            output={"rows": 2},
        )
        run.record(
            "Ran unit tests",
            kind="test",
            input={"suite": "unit"},
            output={"passed": 42, "failed": 0},
        )
        run.record(
            "Ran duplicate-payment regression test",
            kind="test",
            input={"test": "test_duplicate_payment_rejected"},
            output={"passed": 0, "failed": 1},
            status="failed",
            error="AssertionError: duplicate payment was accepted",
            metadata={"implicated_paths": ["payment_service.py"]},
        )
        run.finish("failed")
    return run.id


def _print_timeline(run: Dict[str, Any]) -> None:
    print("%s  %s  [%s]" % (run["id"], run["name"], run["status"]))
    for step in run["steps"]:
        marker = "x" if step["status"] == "failed" else "+"
        print("  %s #%d %-12s %s" % (marker, step["sequence"], step["kind"], step["name"]))
        if step["error"]:
            print("      %s" % step["error"])


def _print_investigation(run: Dict[str, Any]) -> bool:
    result = investigate(run)
    print("Run: %s — %s" % (run["id"], run["name"]))
    if result["failure"] is None:
        print("Failure: none")
        return False
    failure = result["failure"]
    print("Failure: %s" % (failure["error"] or failure["name"]))
    suspect = result.get("suspect")
    if suspect is None:
        print("No suspect found.")
        for line in result["evidence"]:
            print("  %s" % line)
        return False
    else:
        print("First suspect: #%d %s" % (suspect["sequence"], suspect["name"]))
        print("Changed: %s" % result["change"]["path"])
        print("Evidence:")
        for line in result["evidence"]:
            print("  - %s" % line)
        if result["diff"]:
            print("Relevant diff:")
            for line in result["diff"]:
                print("  %s" % line)
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="flightrecorder")
    parser.add_argument("--db", default=DEFAULT_DB, help="SQLite recording path")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="initialize the recording database")
    commands.add_parser("demo", help="record the built-in failing-agent demo")
    agent_demo = commands.add_parser(
        "demo-agent", help="run a real file-edit and subprocess-test workflow"
    )
    agent_demo.add_argument("--workspace", default=".flightrecorder-demo")
    runs = commands.add_parser("runs", help="list recent runs")
    runs.add_argument("--limit", type=int, default=20)
    show = commands.add_parser("show", help="show a run timeline")
    show.add_argument("run_id", nargs="?")
    inv = commands.add_parser("investigate", help="find the first suspect change")
    inv.add_argument("run_id", nargs="?")
    inv.add_argument("--json", action="store_true")
    replay = commands.add_parser("replay", help="replay recorded outputs without side effects")
    replay.add_argument("run_id", nargs="?")
    replay.add_argument("--json", action="store_true")
    compare = commands.add_parser("compare", help="compare two recorded runs")
    compare.add_argument("left_run_id")
    compare.add_argument("right_run_id")
    compare.add_argument("--json", action="store_true")
    export = commands.add_parser("export", help="export a run as JSON or OTLP/JSON")
    export.add_argument("run_id", nargs="?")
    export.add_argument("--format", choices=("json", "otlp"), default="json")
    export.add_argument("--output", default="-", help="output file, or - for stdout")
    serve = commands.add_parser("serve", help="start the local timeline UI")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    prune = commands.add_parser("prune", help="remove recordings outside retention limits")
    prune.add_argument("--older-than-days", type=int, default=30)
    prune.add_argument("--keep-latest", type=int, default=100)
    prune.add_argument(
        "--yes", action="store_true", help="perform deletion; default is dry-run"
    )
    benchmark = commands.add_parser(
        "benchmark", help="measure failure-localization accuracy"
    )
    benchmark.add_argument("--json", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    store = SQLiteStore(args.db)
    if args.command == "init":
        print("Initialized %s" % Path(args.db).resolve())
    elif args.command == "demo":
        run_id = _demo(FlightRecorder(args.db))
        print("Recorded demo run %s" % run_id)
        print("Next: flightrecorder --db %s investigate %s" % (args.db, run_id))
    elif args.command == "demo-agent":
        workspace = Path(args.workspace).resolve()
        run_id = run_agent_demo(FlightRecorder(args.db), workspace)
        print("Recorded real workflow %s" % run_id)
        print("Workspace: %s" % workspace)
        _print_investigation(_load(store, run_id))
    elif args.command == "runs":
        for run in store.list_runs(args.limit):
            print("%-14s %-8s %s" % (run["id"], run["status"], run["name"]))
    elif args.command == "show":
        _print_timeline(_load(store, args.run_id))
    elif args.command == "investigate":
        run = _load(store, args.run_id)
        result = investigate(run)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            _print_investigation(run)
        return 0 if result.get("suspect") is not None else 2
    elif args.command == "replay":
        run = _load(store, args.run_id)
        tape = [
            {
                "sequence": step["sequence"],
                "kind": step["kind"],
                "name": step["name"],
                "input": step["input"],
                "recorded_output": step["output"],
                "status": step["status"],
                "error": step["error"],
            }
            for step in run["steps"]
        ]
        if args.json:
            print(json.dumps(tape, indent=2))
        else:
            print("Controlled replay of %s (side effects disabled)" % run["id"])
            for item in tape:
                print("  #%d %s -> %s" % (item["sequence"], item["name"], item["status"]))
    elif args.command == "compare":
        result = compare_runs(
            _load(store, args.left_run_id), _load(store, args.right_run_id)
        )
        if args.json:
            print(json.dumps(result, indent=2))
        elif result["first_divergence"] is None:
            print("No meaningful divergence found.")
        else:
            first = result["first_divergence"]
            print("First divergence: position #%d" % first["position"])
            print("Reasons: %s" % ", ".join(first["reasons"]))
    elif args.command == "export":
        run = _load(store, args.run_id)
        payload = to_otlp(run) if args.format == "otlp" else to_json(run)
        rendered = json.dumps(payload, indent=2) + "\n"
        if args.output == "-":
            print(rendered, end="")
        else:
            Path(args.output).write_text(rendered, encoding="utf-8")
            print("Exported %s" % Path(args.output).resolve())
    elif args.command == "serve":
        from .web import serve

        try:
            serve(store, args.host, args.port)
        except OSError as exc:
            raise SystemExit(
                "Could not start Flight Recorder on %s:%d: %s. Try another --port."
                % (args.host, args.port, exc)
            )
    elif args.command == "prune":
        cutoff = datetime.now(timezone.utc) - timedelta(
            days=max(args.older_than_days, 0)
        )
        run_ids = store.prune_runs(
            cutoff.isoformat(),
            keep_latest=max(args.keep_latest, 0),
            dry_run=not args.yes,
        )
        action = "Deleted" if args.yes else "Would delete"
        print("%s %d run(s)." % (action, len(run_ids)))
        for run_id in run_ids:
            print("  %s" % run_id)
        if run_ids and not args.yes:
            print("Re-run with --yes to apply.")
    elif args.command == "benchmark":
        result = run_benchmark()
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(
                "Localization benchmark: %d/%d (%d%%)"
                % (result["passed"], result["total"], result["accuracy"] * 100)
            )
            for case in result["cases"]:
                marker = "PASS" if case["passed"] else "FAIL"
                print("  %-4s %s" % (marker, case["name"]))
        return 0 if result["passed"] == result["total"] else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

