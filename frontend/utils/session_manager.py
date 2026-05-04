"""Streamlit session state helpers."""

from __future__ import annotations

from typing import Any

import streamlit as st

from utils.constants import DEFAULT_SEVERITY_FILTERS, DEFAULT_STATUS_FILTERS


SESSION_DEFAULTS: dict[str, Any] = {
    "selected_incident_id": None,
    "incident_ids": [],
    "search_term": "",
    "status_filters": DEFAULT_STATUS_FILTERS.copy(),
    "severity_filters": DEFAULT_SEVERITY_FILTERS.copy(),
    "chat_history": {},
}


def init_session_state() -> None:
    """Initialize session defaults once."""

    for key, value in SESSION_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value


def set_selected_incident(incident_id: str | None) -> None:
    """Persist the selected incident ID."""

    st.session_state.selected_incident_id = incident_id


def set_incident_ids(ids: list[str]) -> None:
    """Persist the ordered list of incidents for next/previous navigation."""

    st.session_state.incident_ids = ids


def get_selected_incident() -> str | None:
    """Return selected incident ID."""

    return st.session_state.get("selected_incident_id")


def get_chat_history(incident_id: str) -> list[dict[str, str]]:
    """Get chat history for a specific incident."""

    history = st.session_state.chat_history
    return history.get(incident_id, [])


def append_chat_message(incident_id: str, role: str, content: str) -> None:
    """Append a chat message to the incident history."""

    history = st.session_state.chat_history
    incident_history = history.get(incident_id, [])
    incident_history.append({"role": role, "content": content})
    history[incident_id] = incident_history
    st.session_state.chat_history = history
