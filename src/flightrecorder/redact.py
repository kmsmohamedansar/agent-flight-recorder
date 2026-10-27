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
        r"(?i)\b(api[_-]?key|password|passwd|secret|access[_-]?token|refresh[_-]?token)"
        r"(\s*[:=]\s*)([^\s,;]+)"
    ),
)


def _normalized(key: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(key).lower()).strip("_")


def _redact_string(value: str) -> str:
    value = _INLINE_PATTERNS[0].sub(r"\1" + REDACTED, value)
    return _INLINE_PATTERNS[1].sub(r"\1\2" + REDACTED, value)


def redact(value: Any) -> Any:
    """Return a JSON-compatible copy with common credentials removed."""
    if isinstance(value, dict):
        return {
            key: REDACTED if _normalized(key) in _SENSITIVE_KEYS else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return _redact_string(value)
    return value

