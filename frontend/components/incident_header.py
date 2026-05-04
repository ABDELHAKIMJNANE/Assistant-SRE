"""Incident metadata header."""

from __future__ import annotations

from typing import Any

import streamlit as st

from services.formatter import format_incident_metadata, severity_style, status_style


def render_incident_header(incident: dict[str, Any]) -> None:
    metadata = format_incident_metadata(incident)
    severity = severity_style(metadata["severity"])
    status = status_style(metadata["status"])

    st.subheader(f"{severity['icon']} {metadata['alert_name']}")
    cols = st.columns(3)
    cols[0].markdown(f"**Pod:** {metadata['pod']}")
    cols[1].markdown(f"**Namespace:** {metadata['namespace']}")
    cols[2].markdown(f"**Created:** {metadata['created_at']}")

    cols = st.columns(3)
    cols[0].markdown(f"**Severity:** {severity['label']}")
    cols[1].markdown(f"**Status:** {status['label']}")
    cols[2].markdown(f"**Incident ID:** {metadata['incident_id']}")
