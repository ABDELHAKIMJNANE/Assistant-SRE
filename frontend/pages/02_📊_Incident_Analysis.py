"""Incident analysis detail page."""

from __future__ import annotations

import streamlit as st

from components.ai_solution import render_ai_solution
from components.approval_buttons import render_approval_section
from components.auto_learning_panel import render_auto_learning_panel
from components.chatbot_section import render_chatbot
from components.incident_header import render_incident_header
from components.incident_overview import render_incident_overview
from components.logs_section import render_logs_section
from components.metrics_section import render_metrics_section
from components.sidebar import render_sidebar
from services.cache import get_incident_detail_cached, get_incidents_cached
from utils.session_manager import get_selected_incident, init_session_state


st.set_page_config(page_title="Incident Analysis | AIOps SRE", layout="wide")
init_session_state()

result = get_incidents_cached(limit=50)
if result.error:
    st.error(result.error)
    incidents = []
else:
    incidents = result.data or []

render_sidebar(incidents)
selected_id = get_selected_incident()

st.title("📊 Incident Analysis")

if not selected_id:
    st.info("Select an incident from the sidebar to begin analysis.")
    st.stop()

detail_result = get_incident_detail_cached(selected_id)
if detail_result.error:
    st.error(detail_result.error)
    st.stop()

incident = detail_result.data or {}

render_incident_header(incident)

overview_tab, log_tab, metrics_tab, solution_tab, chat_tab, approval_tab = st.tabs(
    ["🧭 Overview", "📝 Logs", "📊 Metrics", "🤖 Solution", "💬 Chat", "✅ Approval"]
)

with overview_tab:
    render_incident_overview(incident)
    render_auto_learning_panel(incident)

with log_tab:
    render_logs_section(incident.get("current_logs", []))

with metrics_tab:
    render_metrics_section(incident.get("current_metrics", {}))

with solution_tab:
    render_ai_solution(incident)

with chat_tab:
    render_chatbot(selected_id)

with approval_tab:
    render_approval_section(incident)
