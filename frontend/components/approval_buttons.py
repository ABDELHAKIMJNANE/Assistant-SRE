"""Approval actions for AI solutions — only 'Approve' is available."""

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
    """
    Section d'approbation simplifiée.

    - Si l'incident est déjà résolu : affiche la solution finale validée.
    - Si l'incident est en attente : affiche un bouton 'Approuver'.
      En cliquant, le backend appelle l'IA pour formater la solution finale,
      la sauvegarde dans la DB, et l'affiche ici.
    """
    incident_id = str(incident.get("_id", ""))
    status = incident.get("status", "pending_approval")

    st.markdown("### ✅ Approbation de la solution")

    if status == "résolu":
        st.success("✅ Incident résolu — solution finale validée et enregistrée.")
        validated = incident.get("validated_solution", "")
        if validated:
            st.markdown("**Solution finale approuvée :**")
            st.markdown(validated)
        next_id = _next_incident_id()
        if next_id and st.button("⏭️ Incident suivant"):
            set_selected_incident(next_id)
            st.rerun()
        return

    # Incident en attente d'approbation
    diagnostic = incident.get("diagnostic", {})
    if not diagnostic:
        st.warning("Aucun diagnostic disponible. Attendez que l'analyse IA soit terminée.")
        return

    st.info(
        "L'IA a proposé une solution. Consultez l'onglet **Solution** pour la revoir, "
        "puis cliquez sur **Approuver** ci-dessous.\n\n"
        "Après approbation, l'IA reformatera la solution finale et la sauvegardera en base."
    )

    col_approve, col_next = st.columns([2, 1])

    with col_approve:
        if st.button("✅ Approuver la solution", type="primary", use_container_width=True):
            with st.spinner("🤖 L'IA formate la solution finale…"):
                result = backend_api.approve_incident(incident_id)

            if result.error:
                st.error(f"Erreur lors de l'approbation : {result.error}")
            else:
                data = result.data or {}
                formatted = data.get("formatted_solution", "")
                clear_cache()
                st.success("🎉 Incident approuvé et résolu !")
                if formatted:
                    st.markdown("**Solution finale générée par l'IA :**")
                    st.markdown(formatted)
                st.rerun()

    with col_next:
        next_id = _next_incident_id()
        if next_id and st.button("⏭️ Suivant", use_container_width=True):
            set_selected_incident(next_id)
            st.rerun()
