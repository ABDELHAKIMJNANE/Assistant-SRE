"""Schema Pydantic — Document incident MongoDB / Cosmos DB."""

from datetime import datetime, timezone

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
    labels: dict[str, str] = Field(default_factory=dict)
    message: str = ""
    logs_collected: int = 0
    metrics_collected: int = 0
    past_solution_used: str | None = None
    diagnostic: Diagnostic | None = None
    status: str = "ouvert"
    validated_solution: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: datetime | None = None


class IncidentResponse(BaseModel):
    """Schema de réponse pour un incident (lecture depuis MongoDB)."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    alert_name: str
    state: str = ""
    labels: dict[str, str] = Field(default_factory=dict)
    message: str = ""
    logs_collected: int = 0
    metrics_collected: int = 0
    past_solution_used: str | None = None
    diagnostic: Diagnostic | None = None
    status: str = "ouvert"
    validated_solution: str | None = None
    created_at: datetime | None = None
    resolved_at: datetime | None = None


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
