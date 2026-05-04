"""Logs display section."""

from __future__ import annotations

from typing import Any

import streamlit as st

from config import settings
from services.formatter import format_logs


def render_logs_section(logs: list[str]) -> None:
    st.markdown("### 📝 Logs (latest)")
    formatted_logs = format_logs(logs, settings.max_log_lines)
    if not formatted_logs:
        st.info("No logs available for this incident.")
        return

    st.code("\n".join(formatted_logs), language="text")
    st.download_button(
        label="📥 Download logs",
        data="\n".join(formatted_logs),
        file_name="incident_logs.txt",
        mime="text/plain",
    )
