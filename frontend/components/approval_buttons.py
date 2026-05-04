"""Approval actions for AI solutions."""

from __future__ import annotations

from typing import Any

import streamlit as st

from services import backend_api
from services.cache import clear_cache
from utils.session_manager import get_selected_incident, set_selected_incident


def _next_incident_id() -> str | None:
    incident_ids = st.session_state.get("incident_ids", [])
    current_id = get_selected_incident()
    if current_id and current_id in incident_ids:
        idx = incident_ids.index(current_id)
        if idx + 1 < len(incident_ids):
            return incident_ids[idx + 1]
    return None


def render_approval_section(incident: dict[str, Any]) -> None:
    st.markdown("### ✅ Approval")

    incident_id = str(incident.get("_id", ""))
    status = incident.get("status", "pending")
    diagnostic = incident.get("diagnostic", {})

    solution_key = f"solution_edit_{incident_id}"
    default_solution = incident.get("validated_solution") or diagnostic.get("solution", "")
    edited_solution = st.text_area(
        "Modify solution before approval",
        value=st.session_state.get(solution_key, default_solution),
        height=140,
        key=solution_key,
    )

    note_key = f"approval_note_{incident_id}"
    st.text_input("Approval notes (optional)", key=note_key)

    if status == "résolu":
        st.success("Incident already resolved.")
        return

    cols = st.columns(4)
    if cols[0].button("✅ Approve"):
        result = backend_api.resolve_incident(incident_id, edited_solution)
        if result.error:
            st.error(f"Unable to approve: {result.error}")
        else:
            clear_cache()
            st.success("Incident resolved and saved for Auto-Learning.")
            st.rerun()

    if cols[1].button("❌ Reject"):
        st.warning("Solution rejected locally. No backend update available yet.")

    if cols[2].button("🔄 Modify"):
        st.info("Solution updated locally. Click Approve to persist.")

    next_id = _next_incident_id()
    if cols[3].button("⏭️ Next incident") and next_id:
        set_selected_incident(next_id)
        st.rerun()
