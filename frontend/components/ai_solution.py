"""AI solution rendering."""

from __future__ import annotations

from typing import Any

import streamlit as st

from services.formatter import severity_style


def render_ai_solution(incident: dict[str, Any]) -> None:
    diagnostic = incident.get("diagnostic", {})
    severity = severity_style(str(diagnostic.get("severite", "unknown")).lower())

    st.markdown("### 🤖 AI Proposed Solution")
    st.markdown(f"**Severity:** {severity['icon']} {severity['label']}")
    st.markdown(f"**Category:** {diagnostic.get('categorie', '-')}")

    st.markdown("#### Root Cause")
    st.info(diagnostic.get("cause_racine", "No root cause provided."))

    st.markdown("#### Recommended Solution")
    st.code(diagnostic.get("solution", "No solution provided."), language="bash")

    past_solution = incident.get("past_solution_used")
    if past_solution:
        st.markdown("#### Past Similar Solution")
        st.warning(past_solution)
