"""Sidebar rendering for incidents list and filters."""

from __future__ import annotations

from typing import Any

import streamlit as st

from services.cache import clear_cache
from services.formatter import filter_incidents, incident_label
from utils.constants import DEFAULT_SEVERITY_FILTERS, DEFAULT_STATUS_FILTERS
from utils.session_manager import set_incident_ids, set_selected_incident


def render_sidebar(incidents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Render the sidebar and return filtered incidents."""

    st.sidebar.title("🛰️ SRE Assistant AIOps")
    st.sidebar.caption("Incident monitoring & AI diagnostics")

    search_term = st.sidebar.text_input("Search", value=st.session_state.get("search_term", ""))
    status_filters = st.sidebar.multiselect(
        "Status",
        options=["ouvert", "résolu", "pending", "in_progress"],
        default=st.session_state.get("status_filters", DEFAULT_STATUS_FILTERS),
    )
    severity_filters = st.sidebar.multiselect(
        "Severity",
        options=["critique", "haute", "moyenne", "basse"],
        default=st.session_state.get("severity_filters", DEFAULT_SEVERITY_FILTERS),
    )

    st.session_state.search_term = search_term
    st.session_state.status_filters = status_filters
    st.session_state.severity_filters = severity_filters

    if st.sidebar.button("🔄 Refresh data"):
        clear_cache()
        st.rerun()

    filtered = filter_incidents(incidents, status_filters, severity_filters, search_term)

    if not filtered:
        st.sidebar.info("No incidents match the current filters.")
        set_incident_ids([])
        set_selected_incident(None)
        return filtered

    labels = [incident_label(incident) for incident in filtered]
    ids = [str(incident.get("_id", "")) for incident in filtered]
    set_incident_ids(ids)

    selected_id = st.session_state.get("selected_incident_id")
    if selected_id in ids:
        index = ids.index(selected_id)
    else:
        index = 0
        set_selected_incident(ids[0])

    selection = st.sidebar.radio("Incidents", labels, index=index)
    set_selected_incident(ids[labels.index(selection)])

    return filtered
