"""Read-only Git context capture."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, Optional


def _git(path: Path, *args: str) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), *args],
            text=True,
            capture_output=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def git_state(path: str) -> Optional[Dict[str, Any]]:
    root = _git(Path(path), "rev-parse", "--show-toplevel")
    if not root:
        return None
    root_path = Path(root)
    diff = _git(root_path, "diff", "--no-ext-diff", "--binary") or ""
    staged = _git(root_path, "diff", "--cached", "--no-ext-diff", "--binary") or ""
    return {
        "root": root,
        "commit": _git(root_path, "rev-parse", "HEAD"),
        "branch": _git(root_path, "branch", "--show-current"),
        "status": (_git(root_path, "status", "--short") or "").splitlines(),
        "working_diff": diff[:1_000_000],
        "staged_diff": staged[:1_000_000],
    }

