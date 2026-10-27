"""Deterministic consumption of recorded tool outputs."""

from __future__ import annotations

from typing import Any, Dict, Optional


class ReplayMismatch(RuntimeError):
    pass


class RecordedToolError(RuntimeError):
    pass


class ReplayTape:
    def __init__(self, run: Dict[str, Any]) -> None:
        self.run_id = run["id"]
        self._steps = list(run["steps"])
        self._position = 0

    @property
    def remaining(self) -> int:
        return len(self._steps) - self._position

    def next(self, name: Optional[str] = None) -> Any:
        if self._position >= len(self._steps):
            raise ReplayMismatch("Replay tape %s is exhausted" % self.run_id)
        step = self._steps[self._position]
        if name is not None and step["name"] != name:
            raise ReplayMismatch(
                "Expected step %r, recorded step is %r" % (name, step["name"])
            )
        self._position += 1
        if step["status"] == "failed":
            raise RecordedToolError(step["error"] or "Recorded tool failed")
        return step["output"]

