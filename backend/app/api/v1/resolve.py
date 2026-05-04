"""Resolve endpoint — Validation de la solution par le SRE (bouton Valider)."""

import logging

from fastapi import APIRouter, HTTPException

from app.models.incident import ValidateRequest
from app.services import database

logger = logging.getLogger(__name__)
router = APIRouter()


@router.put("/incidents/{incident_id}/resolve", tags=["Incidents"])
async def resolve_incident(incident_id: str, body: ValidateRequest) -> dict[str, str]:
    """
    L'ingénieur SRE clique sur le bouton 'Valider' dans Streamlit.

    Ce qui se passe :
    1. La solution finale (validée ou modifiée par le SRE) est stockée dans Cosmos DB
    2. Le statut passe à 'résolu'
    3. La date de résolution est enregistrée
    4. L'Auto-Learning pourra utiliser cette solution validée lors de la prochaine
       occurrence de la même alerte

    Le champ 'validated_solution' est la clé de l'Auto-Learning :
    c'est lui qui est retourné par find_past_incident() lors de futures alertes.
    """
    # Vérifier que l'incident existe
    incident = await database.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident non trouvé")

    if incident.get("status") == "résolu":
        raise HTTPException(status_code=400, detail="Incident déjà résolu")

    await database.update_incident_status(
        incident_id=incident_id,
        status="résolu",
        validated_solution=body.validated_solution,
    )

    logger.info(
        f"✅ Incident {incident_id} résolu — "
        f"solution validée: {body.validated_solution[:80]}..."
    )

    return {
        "message": "Incident marqué comme résolu",
        "incident_id": incident_id,
        "validated_solution": body.validated_solution,
    }
