"""Settings and diagnostics page."""

from __future__ import annotations

import streamlit as st

from config import settings
from services import backend_api
from services.cache import clear_cache
from utils.session_manager import init_session_state


st.set_page_config(page_title="Settings | AIOps SRE", layout="wide")
init_session_state()

st.title("⚙️ Settings & Diagnostics")

st.subheader("Backend configuration")

st.write(
    {
        "backend_url": settings.backend_url,
        "request_timeout": settings.request_timeout,
        "cache_ttl_seconds": settings.cache_ttl_seconds,
        "max_log_lines": settings.max_log_lines,
        "max_metrics_points": settings.max_metrics_points,
    }
)

if st.button("🧹 Clear cached data"):
    clear_cache()
    st.success("Cache cleared.")

st.subheader("Connection test")
if st.button("🔍 Test backend connectivity"):
    with st.spinner("Checking backend..."):
        result = backend_api.get_incidents(limit=1)
        if result.error:
            st.error(result.error)
        else:
            st.success("Backend reachable.")
