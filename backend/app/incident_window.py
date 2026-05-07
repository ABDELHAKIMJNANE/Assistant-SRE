"""Incident window resolution helpers."""

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from app.models.investigation import IncidentWindow
from app.models.webhook import AlertPayload


def _normalize_datetime(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        parsed = value
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def resolve_incident_window(
    payload: AlertPayload | Mapping[str, Any],
    lookback_minutes: int = 30,
    forward_minutes: int = 5,
) -> IncidentWindow:
    """Resolve investigation window using firedAt/startsAt timestamps when available."""
    if isinstance(payload, AlertPayload):
        fired_at = _normalize_datetime(payload.fired_at)
        starts_at = _normalize_datetime(payload.starts_at)
    else:
        fired_at = _normalize_datetime(payload.get("firedAt") or payload.get("fired_at"))
        starts_at = _normalize_datetime(payload.get("startsAt") or payload.get("starts_at"))

    anchor = fired_at or starts_at or datetime.now(timezone.utc)
    start = anchor - timedelta(minutes=lookback_minutes)
    end = anchor + timedelta(minutes=forward_minutes)

    return IncidentWindow(
        anchor=anchor,
        start=start,
        end=end,
        lookback_minutes=lookback_minutes,
        forward_minutes=forward_minutes,
    )
