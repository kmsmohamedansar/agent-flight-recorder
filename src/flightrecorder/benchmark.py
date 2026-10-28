"""Deterministic localization benchmark for the investigation heuristic."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .investigate import investigate


def _step(
    sequence: int,
    name: str,
    *,
    path: Optional[str] = None,
    before: str = "",
    after: str = "",
    status: str = "ok",
    error: Optional[str] = None,
    implicated_paths: Optional[List[str]] = None,
) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {}
    if path is not None:
        metadata["changes"] = [{"path": path, "before": before, "after": after}]
    if implicated_paths:
        metadata["implicated_paths"] = implicated_paths
    return {
        "sequence": sequence,
        "name": name,
        "kind": "test" if status == "failed" else "file_write",
        "status": status,
        "error": error,
        "output": None,
        "metadata": metadata,
    }


def _run(run_id: str, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"id": run_id, "name": run_id, "status": "failed", "steps": steps}


CASES = [
    {
        "name": "explicit implicated path beats recency",
        "expected": "payments.py",
        "run": _run(
            "bench-explicit",
            [
                _step(1, "break validation", path="payments.py", before="guard()", after=""),
                _step(2, "unrelated edit", path="formatting.py", before="x=1", after="x=2"),
                _step(3, "test", status="failed", error="duplicate accepted", implicated_paths=["payments.py"]),
            ],
        ),
    },
    {
        "name": "filename in failure output",
        "expected": "src/cache.py",
        "run": _run(
            "bench-filename",
            [
                _step(1, "cache edit", path="src/cache.py", before="ttl=60", after="ttl=0"),
                _step(2, "other edit", path="src/log.py", before="a=1", after="a=2"),
                _step(3, "test", status="failed", error="src/cache.py: stale value"),
            ],
        ),
    },
    {
        "name": "removed vocabulary links cause",
        "expected": "auth.py",
        "run": _run(
            "bench-vocabulary",
            [
                _step(1, "auth edit", path="auth.py", before="validate_token(token)", after="allow(token)"),
                _step(2, "other edit", path="ui.py", before="color='blue'", after="color='red'"),
                _step(3, "test", status="failed", error="validate_token was not called"),
            ],
        ),
    },
    {
        "name": "recent change is fallback",
        "expected": "second.py",
        "run": _run(
            "bench-recency",
            [
                _step(1, "first", path="first.py", before="x=1", after="x=2"),
                _step(2, "second", path="second.py", before="y=1", after="y=2"),
                _step(3, "test", status="failed", error="unexpected result"),
            ],
        ),
    },
    {
        "name": "no file change gives no suspect",
        "expected": None,
        "run": _run(
            "bench-no-change",
            [_step(1, "test", status="failed", error="remote service unavailable")],
        ),
    },
]


def run_benchmark() -> Dict[str, Any]:
    results = []
    for case in CASES:
        result = investigate(case["run"])
        actual = result.get("change", {}).get("path")
        passed = actual == case["expected"]
        results.append(
            {
                "name": case["name"],
                "expected": case["expected"],
                "actual": actual,
                "passed": passed,
            }
        )
    passed_count = sum(1 for result in results if result["passed"])
    return {
        "method": "deterministic-evidence-ranking-v1",
        "passed": passed_count,
        "total": len(results),
        "accuracy": passed_count / len(results),
        "cases": results,
    }
