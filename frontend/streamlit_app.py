"""Main entry point for the Streamlit application."""

from __future__ import annotations

import streamlit as st

from components.sidebar import render_sidebar
from services.cache import get_incidents_cached
from services.formatter import summarize_incidents
from utils.session_manager import get_selected_incident, init_session_state


def main() -> None:
    st.set_page_config(page_title="AIOps SRE Assistant", layout="wide")
    init_session_state()

    st.title("🏢 SRE Assistant AIOps")
    st.caption("AI-assisted incident response with Auto-Learning memory.")

    result = get_incidents_cached(limit=50)
    if result.error:
        st.error(result.error)
        incidents = []
    else:
        incidents = result.data or []

    render_sidebar(incidents)
    summary = summarize_incidents(incidents)

    cols = st.columns(4)
    cols[0].metric("Total incidents", summary["total"])
    cols[1].metric("Open incidents", summary["open"])
    cols[2].metric("Resolved", summary["resolved"])
    cols[3].metric("High/Critical", summary["high"])

    st.markdown("### Quick actions")
    selected_id = get_selected_incident()
    if selected_id:
        if st.button("Go to Incident Analysis"):
            st.switch_page("pages/02_📊_Incident_Analysis.py")
    else:
        st.info("Select an incident in the sidebar to analyze it.")

    st.markdown("### How it works")
    st.write(
        ""
        "1. Grafana triggers alerts → FastAPI collects logs & metrics.\n"
        "2. Azure OpenAI proposes a diagnostic and solution.\n"
        "3. You validate the fix to feed Auto-Learning memory.\n"
        "4. The system reuses past solutions for future incidents."
    )


if __name__ == "__main__":
    main()
