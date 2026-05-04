"""Schema Pydantic — Payload entrant du webhook Grafana."""

from typing import Optional

from pydantic import BaseModel


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

    alert_name: str
    state: str = "alerting"
    labels: dict = {}
    message: str = ""
    dashboard_url: Optional[str] = None
