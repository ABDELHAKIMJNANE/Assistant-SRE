"""Chat endpoint — Chatbot SRE contextuel."""

import logging

from fastapi import APIRouter, HTTPException

from app.models.chat import ChatRequest, ChatResponse
from app.services import database, llm_engine

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat_with_ai(body: ChatRequest):
    """
    Chatbot SRE : l'ingénieur pose une question sur un incident.
    FastAPI re-prompt OpenAI avec le contexte complet de l'incident.

    Exemple :
    - "Est-ce que cette solution va impacter les autres pods ?"
    - "Montre-moi la commande pour vérifier la mémoire actuelle"
    - "Pourquoi le pod redémarre en boucle ?"
    """
    # Récupérer l'incident depuis Cosmos DB
    incident = await database.get_incident(body.incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident non trouvé")

    logger.info(f"💬 Chat sur incident {body.incident_id} — question: {body.question[:80]}")

    answer = await llm_engine.chat_about_incident(
        incident=incident,
        question=body.question,
    )

    return ChatResponse(answer=answer, incident_id=body.incident_id)
