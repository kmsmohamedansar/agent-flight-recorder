"""Run-to-run comparison."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def _signature(step: Dict[str, Any]) -> Tuple[str, str]:
    return step["kind"], step["name"]


def compare_runs(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    """Compare two runs and identify their first meaningful divergence."""
    differences: List[Dict[str, Any]] = []
    maximum = max(len(left["steps"]), len(right["steps"]))
    for index in range(maximum):
        left_step = left["steps"][index] if index < len(left["steps"]) else None
        right_step = right["steps"][index] if index < len(right["steps"]) else None
        reasons: List[str] = []
        if left_step is None or right_step is None:
            reasons.append("step_missing")
        else:
            if _signature(left_step) != _signature(right_step):
                reasons.append("operation_changed")
            if left_step["status"] != right_step["status"]:
                reasons.append("status_changed")
            if left_step["input"] != right_step["input"]:
                reasons.append("input_changed")
            if left_step["output"] != right_step["output"]:
                reasons.append("output_changed")
            if left_step["metadata"].get("changes") != right_step["metadata"].get("changes"):
                reasons.append("file_changes_changed")
        if reasons:
            differences.append(
                {
                    "position": index + 1,
                    "reasons": reasons,
                    "left": left_step,
                    "right": right_step,
                }
            )
    return {
        "left_run_id": left["id"],
        "right_run_id": right["id"],
        "status_changed": left["status"] != right["status"],
        "first_divergence": differences[0] if differences else None,
        "differences": differences,
    }

