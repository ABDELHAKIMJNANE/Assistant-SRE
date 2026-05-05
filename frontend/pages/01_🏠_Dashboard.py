"""Dashboard page showing incidents list and stats."""

from __future__ import annotations

import streamlit as st

from components.sidebar import render_sidebar
from services.cache import get_incidents_cached
from services.formatter import summarize_incidents
from utils.session_manager import init_session_state


st.set_page_config(page_title="Dashboard | AIOps SRE", layout="wide")
init_session_state()

st.title("🏠 Incident Dashboard")

result = get_incidents_cached(limit=50)
if result.error:
    st.error(result.error)
    incidents = []
else:
    incidents = result.data or []

filtered = render_sidebar(incidents)
summary = summarize_incidents(incidents)

cols = st.columns(4)
cols[0].metric("Total", summary["total"])
cols[1].metric("Open", summary["open"])
cols[2].metric("Resolved", summary["resolved"])
cols[3].metric("High/Critical", summary["high"])

st.markdown("### Latest incidents")
if not filtered:
    st.info("No incidents to display.")
else:
    table_rows = []
    for incident in filtered:
        labels = incident.get("labels", {})
        table_rows.append(
            {
                "Alert": incident.get("alert_name"),
                "Pod": labels.get("pod"),
                "Namespace": labels.get("namespace"),
                "Status": incident.get("status"),
                "Severity": incident.get("diagnostic", {}).get("severite"),
                "Created": incident.get("created_at"),
            }
        )
    st.dataframe(table_rows, use_container_width=True)

st.caption("Select an incident from the sidebar to analyze it in detail.")
