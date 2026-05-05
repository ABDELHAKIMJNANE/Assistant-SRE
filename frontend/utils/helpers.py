"""Utility helpers for formatting and safety."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Sequence


def safe_get(mapping: dict[str, Any], key: str, default: Any = "") -> Any:
    """Safely read a key from a mapping."""

    return mapping.get(key, default) if isinstance(mapping, dict) else default


def format_datetime(value: Any) -> str:
    """Format datetime values for display."""

    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S UTC")
    if isinstance(value, str) and value:
        return value.replace("T", " ").replace("Z", " UTC")
    return "-"


def clamp_list(items: Sequence[Any] | None, limit: int) -> list[Any]:
    """Return the last N items of a list-like sequence."""

    if not items:
        return []
    return list(items[-limit:])


def to_lower(value: Any) -> str:
    """Normalize text to lower-case string."""

    return str(value).strip().lower()


def ensure_list(value: Any) -> list[Any]:
    """Coerce a value into a list."""

    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, dict)):
        return list(value)
    return [value]
