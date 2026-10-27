"""Bounded local file snapshots for automatic change detection."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Optional


MAX_CAPTURE_BYTES = 1_000_000
IGNORED_PARTS = {".git", ".venv", "__pycache__", ".pytest_cache"}


def _eligible(path: Path) -> bool:
    return not any(part in IGNORED_PARTS for part in path.parts) and not path.name.startswith(
        ".flightrecorder.sqlite"
    )


def _read(path: Path) -> Optional[str]:
    try:
        if path.stat().st_size > MAX_CAPTURE_BYTES:
            return None
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def snapshot(paths: Iterable[str]) -> Dict[str, Optional[str]]:
    result: Dict[str, Optional[str]] = {}
    for raw_path in paths:
        path = Path(raw_path).expanduser().resolve()
        if path.is_file() and _eligible(path):
            result[str(path)] = _read(path)
        elif path.is_dir():
            for child in path.rglob("*"):
                if child.is_file() and _eligible(child):
                    content = _read(child)
                    if content is not None:
                        result[str(child)] = content
        elif not path.exists() and _eligible(path):
            result[str(path)] = None
    return result


def changes(
    before: Dict[str, Optional[str]], after: Dict[str, Optional[str]]
) -> Dict[str, Dict[str, Optional[str]]]:
    return {
        path: {"before": before.get(path), "after": after.get(path)}
        for path in sorted(set(before) | set(after))
        if before.get(path) != after.get(path)
    }

