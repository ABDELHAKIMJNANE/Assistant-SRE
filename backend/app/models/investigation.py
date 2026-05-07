"""Pydantic models for the LangGraph investigation pipeline state."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IncidentWindow(BaseModel):
    """Resolved incident investigation window."""

    anchor: datetime
    start: datetime
    end: datetime
    lookback_minutes: int
    forward_minutes: int


class InvestigationState(BaseModel):
    """State persisted across LangGraph investigation nodes."""

    alert_name: str
    state: str = "alerting"
    labels: dict[str, str] = Field(default_factory=dict)
    message: str = ""
    dashboard_url: str | None = None
    incident_window: IncidentWindow | None = None
    raw_logs: list[str] = Field(default_factory=list)
    raw_metrics: dict[str, float] = Field(default_factory=dict)
    redacted_logs: list[str] = Field(default_factory=list)
    redacted_metrics: dict[str, float] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)
    redaction_map: dict[str, str] = Field(default_factory=dict)
    diagnostic: dict[str, Any] | None = None
    solution_steps: list[str] = Field(default_factory=list)
    final_solution: str = ""
    confidence_score: float = 0.0
    past_solution: str | None = None
