"""Incident overview and context details."""

from __future__ import annotations

from typing import Any

import streamlit as st

from services.formatter import format_incident_metadata
from utils.helpers import format_datetime


def _render_labels(labels: dict[str, Any]) -> None:
    if not labels:
        st.info("No labels available for this incident.")
        return

    rows = [{"Label": key, "Value": value} for key, value in labels.items()]
    st.dataframe(rows, use_container_width=True)


def render_incident_overview(incident: dict[str, Any]) -> None:
    """Render incident metadata, alert message, and labels."""

    metadata = format_incident_metadata(incident)
    st.markdown("### 🧭 Incident Overview")

    cols = st.columns(4)
    cols[0].metric("State", incident.get("state", "-") or "-")
    cols[1].metric("Logs collected", str(incident.get("logs_collected", 0)))
    cols[2].metric("Metrics collected", str(incident.get("metrics_collected", 0)))
    cols[3].metric("Created", metadata["created_at"])

    resolved_at = format_datetime(incident.get("resolved_at"))
    st.markdown(f"**Resolved at:** {resolved_at}")

    st.markdown("#### Alert message")
    message = incident.get("message", "").strip()
    if message:
        st.info(message)
    else:
        st.info("No alert message provided.")

    st.markdown("#### Labels")
    _render_labels(incident.get("labels", {}))
