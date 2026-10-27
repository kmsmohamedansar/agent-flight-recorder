"""Evidence-based first-suspect localization for a recorded run."""

from __future__ import annotations

import difflib
import re
from typing import Any, Dict, List, Optional, Tuple


def _failure(run: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return next((step for step in run["steps"] if step["status"] == "failed"), None)


def _changed_lines(before: Optional[str], after: Optional[str]) -> List[str]:
    before_lines = (before or "").splitlines()
    after_lines = (after or "").splitlines()
    return list(
        difflib.unified_diff(before_lines, after_lines, lineterm="", n=1)
    )


def investigate(run: Dict[str, Any]) -> Dict[str, Any]:
    failure = _failure(run)
    if failure is None:
        return {"failure": None, "suspect": None, "evidence": ["No failed step recorded."]}

    implicated = set(failure["metadata"].get("implicated_paths", []))
    failure_text = "%s %s" % (failure.get("error") or "", failure.get("output") or "")
    candidates: List[Tuple[int, int, Dict[str, Any], Dict[str, Any]]] = []
    for step in run["steps"]:
        if step["sequence"] >= failure["sequence"]:
            break
        for change in step["metadata"].get("changes", []):
            score = step["sequence"]
            if change.get("path") in implicated:
                score += 10_000
            path = change.get("path", "")
            if path and (path in failure_text or path.rsplit("/", 1)[-1] in failure_text):
                score += 5_000
            removed = " ".join(
                line[1:].strip()
                for line in _changed_lines(change.get("before"), change.get("after"))
                if line.startswith("-") and not line.startswith("---")
            )
            failure_words = set(re.findall(r"[A-Za-z_]{4,}", failure_text.lower()))
            removed_words = set(re.findall(r"[A-Za-z_]{4,}", removed.lower()))
            score += min(len(failure_words & removed_words), 20) * 100
            candidates.append((score, step["sequence"], step, change))

    if not candidates:
        return {
            "failure": failure,
            "suspect": None,
            "evidence": ["No earlier recorded file change can be linked to the failure."],
        }

    _, _, step, change = max(candidates, key=lambda item: (item[0], item[1]))
    diff = _changed_lines(change.get("before"), change.get("after"))
    evidence = [
        "The change occurred before the failing step.",
        "The failing step directly implicated this path."
        if change.get("path") in implicated
        else (
            "The failure output names this changed path."
            if change.get("path") in failure_text
            or change.get("path", "").rsplit("/", 1)[-1] in failure_text
            else "This was the highest-scoring recorded change before the failure."
        ),
    ]
    return {
        "failure": failure,
        "suspect": step,
        "change": change,
        "diff": diff,
        "evidence": evidence,
        "method": "deterministic-evidence-ranking-v1",
    }

