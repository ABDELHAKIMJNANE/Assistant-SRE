"""Tests for incident window resolver."""

from datetime import datetime, timezone

from app.incident_window import resolve_incident_window
from app.models.webhook import AlertPayload


def test_resolve_incident_window_prefers_fired_at() -> None:
    payload = AlertPayload(
        alert_name="OOMKilled",
        startsAt="2026-05-07T10:00:00Z",
        firedAt="2026-05-07T10:05:00Z",
    )

    window = resolve_incident_window(payload, lookback_minutes=30, forward_minutes=5)

    assert window.anchor == datetime(2026, 5, 7, 10, 5, tzinfo=timezone.utc)
    assert window.start == datetime(2026, 5, 7, 9, 35, tzinfo=timezone.utc)
    assert window.end == datetime(2026, 5, 7, 10, 10, tzinfo=timezone.utc)


def test_resolve_incident_window_defaults_to_now_when_missing_timestamps() -> None:
    payload = AlertPayload(alert_name="OOMKilled")
    window = resolve_incident_window(payload)

    assert window.anchor.tzinfo is not None
    assert window.start < window.anchor < window.end
