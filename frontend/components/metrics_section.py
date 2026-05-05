"""Metrics display section."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from config import settings
from services.formatter import format_metrics


def render_metrics_section(metrics: Any) -> None:
    st.markdown("### 📊 Metrics")
    formatted = format_metrics(metrics, settings.max_metrics_points)
    if not formatted:
        st.info("No metrics available for this incident.")
        return

    if isinstance(metrics, dict):
        memory_bytes = metrics.get("memory_usage_bytes")
        cpu_seconds = metrics.get("cpu_usage_seconds")
        restarts = metrics.get("restart_count")
        cols = st.columns(3)
        if memory_bytes is not None:
            cols[0].metric("Memory (MiB)", f"{memory_bytes / (1024 * 1024):.1f}")
        if cpu_seconds is not None:
            cols[1].metric("CPU seconds", f"{cpu_seconds:.1f}")
        if restarts is not None:
            cols[2].metric("Restarts", f"{int(restarts)}")

    df = pd.DataFrame(formatted)
    st.dataframe(df, use_container_width=True)

    st.download_button(
        label="📥 Download metrics",
        data=df.to_csv(index=False),
        file_name="incident_metrics.csv",
        mime="text/csv",
    )
