"""Schema Pydantic — Payload entrant du webhook Grafana."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AlertPayload(BaseModel):
    """
    Structure du JSON envoyé par Grafana quand une alerte se déclenche.
    Exemple :
    {
        "alert_name": "OOMKilled",
        "state": "alerting",
        "labels": {"pod": "fastapi-demo-xxx", "namespace": "app-demo"},
        "message": "Container killed due to OOM"
    }
    """

    model_config = ConfigDict(populate_by_name=True)

    alert_name: str
    state: str = "alerting"
    labels: dict[str, str] = Field(default_factory=dict)
    message: str = ""
    dashboard_url: str | None = None
    starts_at: datetime | None = Field(default=None, alias="startsAt")
    fired_at: datetime | None = Field(default=None, alias="firedAt")
