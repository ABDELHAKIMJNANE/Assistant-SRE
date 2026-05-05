"""Caching layer for backend requests."""

from __future__ import annotations

import streamlit as st

from config import settings
from services import backend_api


@st.cache_data(ttl=settings.cache_ttl_seconds, show_spinner=False)
def get_incidents_cached(skip: int = 0, limit: int = 50):
    return backend_api.get_incidents(skip=skip, limit=limit)


@st.cache_data(ttl=settings.cache_ttl_seconds, show_spinner=False)
def get_incident_detail_cached(incident_id: str):
    return backend_api.get_incident_detail(incident_id)


def clear_cache() -> None:
    st.cache_data.clear()
