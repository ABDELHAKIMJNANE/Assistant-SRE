"""Formatting helpers for backend data."""

from __future__ import annotations

from typing import Any

from utils.constants import SEVERITY_STYLES, STATUS_STYLES
from utils.helpers import clamp_list, format_datetime, to_lower


def incident_severity(incident: dict[str, Any]) -> str:
    diagnostic = incident.get("diagnostic", {}) if isinstance(incident, dict) else {}
    return to_lower(diagnostic.get("severite", "unknown"))


def incident_status(incident: dict[str, Any]) -> str:
    return to_lower(incident.get("status", "pending"))


def severity_style(severity: str) -> dict[str, str]:
    return SEVERITY_STYLES.get(severity, SEVERITY_STYLES["unknown"])


def status_style(status: str) -> dict[str, str]:
    return STATUS_STYLES.get(status, STATUS_STYLES["pending"])


def incident_label(incident: dict[str, Any]) -> str:
    alert_name = incident.get("alert_name", "Unknown")
    pod = incident.get("labels", {}).get("pod", "pod-?")
    severity = severity_style(incident_severity(incident))
    status = status_style(incident_status(incident))
    return f"{severity['icon']} {alert_name} • {pod} • {severity['label']} / {status['label']}"


def filter_incidents(
    incidents: list[dict[str, Any]],
    status_filters: list[str],
    severity_filters: list[str],
    search_term: str,
) -> list[dict[str, Any]]:
    search_term = to_lower(search_term)
    filtered = []
    for incident in incidents:
        status = incident_status(incident)
        severity = incident_severity(incident)
        if status_filters and status not in status_filters:
            continue
        if severity_filters and severity not in severity_filters:
            continue
        haystack = " ".join(
            [
                str(incident.get("alert_name", "")),
                str(incident.get("labels", {}).get("pod", "")),
                str(incident.get("labels", {}).get("namespace", "")),
                str(incident.get("_id", "")),
            ]
        ).lower()
        if search_term and search_term not in haystack:
            continue
        filtered.append(incident)
    return filtered


def summarize_incidents(incidents: list[dict[str, Any]]) -> dict[str, int]:
    summary = {"total": len(incidents), "open": 0, "resolved": 0, "high": 0}
    for incident in incidents:
        status = incident_status(incident)
        severity = incident_severity(incident)
        if status == "ouvert":
            summary["open"] += 1
        if status == "résolu":
            summary["resolved"] += 1
        if severity in {"haute", "critique"}:
            summary["high"] += 1
    return summary


def format_incident_metadata(incident: dict[str, Any]) -> dict[str, str]:
    labels = incident.get("labels", {})
    created_at = format_datetime(incident.get("created_at"))
    return {
        "alert_name": incident.get("alert_name", "-"),
        "pod": labels.get("pod", "-"),
        "namespace": labels.get("namespace", "-"),
        "status": incident_status(incident),
        "severity": incident_severity(incident),
        "incident_id": incident.get("_id", "-"),
        "created_at": created_at,
    }


def format_logs(logs: list[str], max_lines: int) -> list[str]:
    return clamp_list(logs, max_lines)


def format_metrics(metrics: Any, max_points: int) -> list[dict[str, Any]]:
    if isinstance(metrics, list):
        return clamp_list(metrics, max_points)
    if isinstance(metrics, dict):
        formatted = []
        for key, value in metrics.items():
            formatted.append({"metric": key, "value": value})
        return formatted[:max_points]
    return []
