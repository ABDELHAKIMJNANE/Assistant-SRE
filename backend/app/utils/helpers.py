"""Helper utility functions."""
from datetime import datetime
from typing import Any, Optional


def serialize_datetime(dt: Optional[datetime]) -> Optional[str]:
    """Serialize datetime to ISO 8601 string."""
    if dt is None:
        return None
    return dt.isoformat()


def truncate_string(text: str, max_length: int = 200) -> str:
    """Truncate a string to max_length, adding ellipsis if truncated."""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def safe_get_nested(data: dict, *keys: str, default: Any = None) -> Any:
    """Safely get a nested dictionary value."""
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key, default)
    return current


def format_bytes(num_bytes: float) -> str:
    """Format bytes to human-readable string."""
    for unit in ["B", "Ki", "Mi", "Gi"]:
        if num_bytes < 1024.0:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} Ti"
