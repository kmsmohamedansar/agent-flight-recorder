"""Portable JSON and OpenTelemetry-shaped exports."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Dict, List

from . import __version__


def _nanos(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return str(int(parsed.timestamp() * 1_000_000_000))


def _trace_id(run_id: str) -> str:
    return hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:32]


def _span_id(run_id: str, sequence: int) -> str:
    value = "%s:%d" % (run_id, sequence)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def to_otlp(run: Dict[str, Any]) -> Dict[str, Any]:
    """Return OTLP/JSON-compatible span data without requiring an OTEL SDK."""
    trace_id = _trace_id(run["id"])
    spans: List[Dict[str, Any]] = []
    for step in run["steps"]:
        attributes = [
            {"key": "agent.run.id", "value": {"stringValue": run["id"]}},
            {"key": "agent.step.kind", "value": {"stringValue": step["kind"]}},
            {"key": "agent.step.sequence", "value": {"intValue": str(step["sequence"])}},
        ]
        span = {
            "traceId": trace_id,
            "spanId": _span_id(run["id"], step["sequence"]),
            "name": step["name"],
            "kind": 1,
            "startTimeUnixNano": _nanos(step["started_at"]),
            "endTimeUnixNano": _nanos(step["finished_at"]),
            "attributes": attributes,
            "status": {
                "code": 2 if step["status"] == "failed" else 1,
                "message": step["error"] or "",
            },
        }
        spans.append(span)
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {
                            "key": "service.name",
                            "value": {"stringValue": "agent-flight-recorder"},
                        }
                    ]
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "flightrecorder", "version": __version__},
                        "spans": spans,
                    }
                ],
            }
        ]
    }


def to_json(run: Dict[str, Any]) -> Dict[str, Any]:
    return {"schema_version": 1, "run": run}

