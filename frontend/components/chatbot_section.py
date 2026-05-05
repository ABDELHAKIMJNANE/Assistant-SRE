"""Chat interface for AI interaction."""

from __future__ import annotations

import streamlit as st

from services import backend_api
from utils.session_manager import append_chat_message, get_chat_history


def render_chatbot(incident_id: str) -> None:
    st.markdown("### 💬 Chat with AI Engineer")

    history = get_chat_history(incident_id)
    for message in history:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    prompt = st.chat_input("Ask a question about this incident")
    if not prompt:
        return

    append_chat_message(incident_id, "user", prompt)
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        with st.spinner("AI is analyzing..."):
            result = backend_api.chat_incident(incident_id, prompt)
            if result.error:
                response = f"Error contacting AI: {result.error}"
            else:
                response = result.data.get("answer", "No response provided.")
            st.write(response)
            append_chat_message(incident_id, "assistant", response)
