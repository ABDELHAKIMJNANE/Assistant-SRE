"""Auto-learning memory panel."""

from __future__ import annotations

from typing import Any

import streamlit as st

from services.formatter import incident_status, status_style
from utils.helpers import format_datetime


def render_auto_learning_panel(incident: dict[str, Any]) -> None:
    """Render Auto-Learning context and validated solutions."""

    st.markdown("### 🧠 Auto-Learning Memory")

    status = incident_status(incident)
    status_display = status_style(status)
    st.markdown(f"**Current status:** {status_display['icon']} {status_display['label']}")

    past_solution = incident.get("past_solution_used")
    validated_solution = incident.get("validated_solution")
    resolved_at = format_datetime(incident.get("resolved_at"))

    cols = st.columns(2)
    cols[0].markdown(f"**Resolved at:** {resolved_at}")
    cols[1].markdown(f"**Auto-learning ready:** {'Yes' if status == 'résolu' else 'No'}")

    if past_solution:
        st.markdown("#### Past solution reused")
        st.warning(past_solution)
    else:
        st.info("No past solution was reused for this incident.")

    if validated_solution:
        st.markdown("#### Validated solution")
        st.success(validated_solution)
    elif status == "résolu":
        st.info("Incident resolved but no validated solution recorded.")
    else:
        st.info("Validate a solution to store it for Auto-Learning.")
