"""AI solution rendering."""

from __future__ import annotations

from typing import Any

import streamlit as st

from services.formatter import severity_style


def render_ai_solution(incident: dict[str, Any]) -> None:
    diagnostic = incident.get("diagnostic", {})
    severity = severity_style(str(diagnostic.get("severite", "unknown")).lower())

    st.markdown("### 🤖 Solution proposée par l'IA")
    st.markdown(f"**Sévérité :** {severity['icon']} {severity['label']}")
    st.markdown(f"**Catégorie :** `{diagnostic.get('categorie', '-')}`")

    st.markdown("#### 🔍 Cause racine")
    st.info(diagnostic.get("cause_racine", "Aucune cause racine fournie."))

    st.markdown("#### 💡 Solution recommandée")
    st.code(diagnostic.get("solution", "Aucune solution fournie."), language="bash")

    actions = diagnostic.get("actions_immediates", [])
    if actions:
        st.markdown("#### ⚡ Actions immédiates")
        for i, action in enumerate(actions, 1):
            st.markdown(f"{i}. {action}")

    prevention = diagnostic.get("prevention", "")
    if prevention:
        st.markdown("#### 🛡️ Prévention")
        st.success(prevention)

    past_solution = incident.get("past_solution_used")
    if past_solution:
        st.markdown("#### 🔄 Solution similaire passée (Auto-Learning)")
        st.warning(past_solution)

    validated = incident.get("validated_solution")
    if validated and incident.get("status") == "résolu":
        st.markdown("#### ✅ Solution finale validée")
        st.markdown(validated)
