"""Schema Pydantic — Document incident MongoDB / Cosmos DB."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class Diagnostic(BaseModel):
    """Résultat de l'analyse IA (Azure OpenAI)."""

    cause_racine: str
    solution: str
    severite: str = "moyenne"
    categorie: str = "unknown"


class IncidentCreate(BaseModel):
    """Document inséré dans MongoDB lors de la création d'un incident."""

    alert_name: str
    state: str
    labels: dict = {}
    message: str = ""
    logs_collected: int = 0
    metrics_collected: int = 0
    past_solution_used: Optional[str] = None
    diagnostic: Optional[Diagnostic] = None
    status: str = "ouvert"
    validated_solution: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None


class IncidentResponse(BaseModel):
    """Schema de réponse pour un incident (lecture depuis MongoDB)."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    alert_name: str
    state: str = ""
    labels: dict = {}
    message: str = ""
    logs_collected: int = 0
    metrics_collected: int = 0
    past_solution_used: Optional[str] = None
    diagnostic: Optional[Diagnostic] = None
    status: str = "ouvert"
    validated_solution: Optional[str] = None
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None


class ValidateRequest(BaseModel):
    """
    Corps de la requête PUT /incidents/{id}/resolve.
    L'ingénieur SRE clique sur le bouton 'Valider' après avoir
    confirmé (ou modifié) la solution proposée par l'IA.
    La solution validée est stockée dans Cosmos DB pour l'Auto-Learning.
    """

    validated_solution: str = Field(
        ...,
        description="La solution finale validée par l'ingénieur SRE. "
        "Peut être la solution IA telle quelle, ou modifiée par le SRE.",
        examples=["kubectl set resources deployment/fastapi-demo -c fastapi --limits=memory=512Mi"],
    )
