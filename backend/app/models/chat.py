"""Schema Pydantic — Message chatbot SRE."""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """
    Requête du chatbot SRE.
    L'ingénieur pose une question à propos d'un incident spécifique.
    FastAPI re-prompt OpenAI avec le contexte de l'incident.
    """

    incident_id: str = Field(
        ..., description="ID de l'incident concerné"
    )
    question: str = Field(
        ...,
        description="Question posée par l'ingénieur SRE",
        examples=["Est-ce que cette solution va impacter les autres pods ?"],
    )


class ChatResponse(BaseModel):
    """Réponse du chatbot."""

    answer: str
    incident_id: str
