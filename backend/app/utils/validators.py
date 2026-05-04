"""Custom validators for data validation."""
import re
from typing import Any


def validate_object_id(value: str) -> str:
    """Validate MongoDB ObjectId format."""
    if not re.match(r'^[0-9a-fA-F]{24}$', value):
        raise ValueError(f"'{value}' is not a valid ObjectId")
    return value


def validate_non_empty_string(value: str) -> str:
    """Validate that a string is not empty or whitespace-only."""
    if not value or not value.strip():
        raise ValueError("String cannot be empty or whitespace-only")
    return value.strip()


def validate_alert_name(value: str) -> str:
    """Validate Grafana alert name."""
    value = validate_non_empty_string(value)
    if len(value) > 255:
        raise ValueError("Alert name cannot exceed 255 characters")
    return value


def validate_log_lines(logs: list[str], max_lines: int = 1000) -> list[str]:
    """Validate log list does not exceed maximum lines."""
    return logs[:max_lines]
