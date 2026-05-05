"""Shared UI constants and mappings."""

from __future__ import annotations

from typing import Final

SEVERITY_STYLES: Final = {
    "critique": {"label": "CRITIQUE", "icon": "🔴", "color": "#dc2626"},
    "haute": {"label": "HIGH", "icon": "🟥", "color": "#ef4444"},
    "moyenne": {"label": "MEDIUM", "icon": "🟠", "color": "#f97316"},
    "basse": {"label": "LOW", "icon": "🟢", "color": "#16a34a"},
    "unknown": {"label": "UNKNOWN", "icon": "⚪", "color": "#64748b"},
}

STATUS_STYLES: Final = {
    "ouvert": {"label": "OPEN", "icon": "🔴", "color": "#dc2626"},
    "résolu": {"label": "RESOLVED", "icon": "🟢", "color": "#16a34a"},
    "in_progress": {"label": "IN PROGRESS", "icon": "🟠", "color": "#f97316"},
    "pending": {"label": "PENDING", "icon": "🟡", "color": "#eab308"},
}

DEFAULT_STATUS_FILTERS: Final = ["ouvert", "résolu"]
DEFAULT_SEVERITY_FILTERS: Final = ["critique", "haute", "moyenne", "basse"]

LOG_LEVEL_ICONS: Final = {
    "ERROR": "🔴",
    "WARN": "🟠",
    "WARNING": "🟠",
    "INFO": "🔵",
    "DEBUG": "⚪",
}
