import streamlit as st
import httpx
import os
from dotenv import load_dotenv
from datetime import datetime

# Charger les variables d'environnement
load_dotenv()
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000/api/v1")

st.set_page_config(page_title="AIOps SRE Assistant", layout="wide")

# ─── Fonctions de communication avec le Backend ───

def get_incidents():
    """Récupérer la liste des incidents depuis le backend."""
    try:
        with httpx.Client() as client:
            response = client.get(f"{BACKEND_URL}/incidents")
            return response.json()
    except Exception as e:
        st.error(f"Erreur de connexion au backend : {e}")
        return []

def get_incident_detail(incident_id):
    """Récupérer les détails d'un incident."""
    with httpx.Client() as client:
        response = client.get(f"{BACKEND_URL}/incidents/{incident_id}")
        return response.json()

def validate_solution(incident_id, solution):
    """Appeler l'endpoint de résolution (Bouton Valider)."""
    with httpx.Client() as client:
        response = client.put(
            f"{BACKEND_URL}/incidents/{incident_id}/resolve",
            json={"validated_solution": solution}
        )
        return response.status_code == 200

def ask_chat(incident_id, question):
    """Poser une question au chatbot."""
    with httpx.Client() as client:
        response = client.post(
            f"{BACKEND_URL}/chat",
            json={"incident_id": incident_id, "question": question}
        )
        return response.json().get("answer", "Erreur de réponse.")

# ─── Interface Utilisateur ───

st.title("🛡️ Assistant SRE AIOps")

# 1. Barre latérale : Index des incidents
st.sidebar.header("📋 Index des Incidents")
incidents = get_incidents()

if not incidents:
    st.sidebar.write("Aucun incident trouvé.")
    selected_incident_id = None
else:
    # Créer une liste de labels pour le selectbox
    incident_options = {
        f"{i.get('alert_name')} - {i.get('labels', {}).get('pod', 'N/A')}": i.get('_id')
        for i in incidents
    }
    selected_label = st.sidebar.radio("Sélectionnez un incident :", list(incident_options.keys()))
    selected_incident_id = incident_options[selected_label]

# 2. Zone principale
if selected_incident_id:
    # Récupérer les détails complets
    detail = get_incident_detail(selected_incident_id)
    
    col1, col2 = st.columns([2, 1])

    with col1:
        st.header(f"Incident : {detail.get('alert_name')}")
        st.write(f"**Statut :** `{detail.get('status')}`")
        
        # Diagnostic IA
        diag = detail.get("diagnostic", {})
        with st.expander("🤖 Diagnostic de l'IA", expanded=True):
            st.subheader("Cause Racine")
            st.info(diag.get("cause_racine", "N/A"))
            
            st.subheader("Solution proposée")
            solution_text = st.text_area("Éditer la solution avant validation :", diag.get("solution", "N/A"), height=100)
            
            if detail.get("status") == "ouvert":
                if st.button("✅ Valider la solution (Apprendre)"):
                    if validate_solution(selected_incident_id, solution_text):
                        st.success("Incident résolu ! L'Auto-Learning a été mis à jour.")
                        st.rerun()
            else:
                st.success(f"Incident résolu. Solution validée : {detail.get('validated_solution')}")

        # Logs et Métriques (Index des preuves)
        st.subheader("📊 Preuves (Logs & Métriques)")
        tab1, tab2 = st.tabs(["Logs Loki", "Métriques Prometheus"])
        
        with tab1:
            logs = detail.get("current_logs", [])
            if logs:
                st.code("\n".join(logs), language="text")
            else:
                st.write("Aucun log trouvé.")
        
        with tab2:
            metrics = detail.get("current_metrics", {})
            if metrics:
                st.json(metrics)
            else:
                st.write("Aucune métrique trouvée.")

    with col2:
        st.subheader("💬 Chat avec l'Expert IA")
        st.write("Posez des questions sur cet incident spécifique.")
        
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        # Afficher l'historique du chat
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        # Input du chat
        if prompt := st.chat_input("Votre question (ex: Quel est l'impact de ce crash ?)"):
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.write(prompt)
            
            with st.chat_message("assistant"):
                with st.spinner("L'IA réfléchit..."):
                    answer = ask_chat(selected_incident_id, prompt)
                    st.write(answer)
                    st.session_state.chat_history.append({"role": "assistant", "content": answer})

else:
    st.info("Sélectionnez un incident dans la barre latérale pour commencer l'analyse.")
