"""Conservative secret redaction for persisted recordings."""

from __future__ import annotations

import re
from typing import Any


REDACTED = "<redacted>"

_SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "client_secret",
    "cookie",
    "password",
    "passwd",
    "refresh_token",
    "secret",
    "set_cookie",
    "token",
    "access_token",
    "x_api_key",
}

_INLINE_PATTERNS = (
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+"),
    re.compile(
        r"(?i)\b([A-Za-z0-9_]*(?:api[_-]?key|password|passwd|secret|token)[A-Za-z0-9_]*)"
        r"(\s*[:=]\s*)([^\s,;]+)"
    ),
    re.compile(r"(?i)([a-z][a-z0-9+.-]*://[^:/\s]+:)([^@\s/]+)(@)"),
    re.compile(
        r"(?i)\b(?:ghp_[A-Za-z0-9]{8,}|github_pat_[A-Za-z0-9_]{8,}|"
        r"sk-[A-Za-z0-9_-]{8,}|xox[bap]-[A-Za-z0-9-]{8,}|AKIA[A-Z0-9]{12,})\b"
    ),
)


def _normalized(key: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(key).lower()).strip("_")


def _redact_string(value: str) -> str:
    value = _INLINE_PATTERNS[0].sub(r"\1" + REDACTED, value)
    value = _INLINE_PATTERNS[1].sub(r"\1\2" + REDACTED, value)
    value = _INLINE_PATTERNS[2].sub(r"\1" + REDACTED + r"\3", value)
    return _INLINE_PATTERNS[3].sub(REDACTED, value)


def _sensitive_key(key: Any) -> bool:
    normalized = _normalized(key)
    if normalized in _SENSITIVE_KEYS:
        return True
    parts = set(normalized.split("_"))
    return bool(parts & {"password", "passwd", "secret", "token"})


def redact(value: Any) -> Any:
    """Return a JSON-compatible copy with common credentials removed."""
    if isinstance(value, dict):
        return {
            key: REDACTED if _sensitive_key(key) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return _redact_string(value)
    return value

