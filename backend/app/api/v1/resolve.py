"""Resolve endpoint — Approbation de l'incident par le SRE."""

import logging

from fastapi import APIRouter, HTTPException

from app.models.incident import ValidateRequest
from app.services import database, llm_engine

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/incidents/{incident_id}/approve", tags=["Incidents"])
async def approve_incident(incident_id: str) -> dict:
    """
    Étape 1 : le SRE clique sur 'Approuver' dans le frontend.

    L'IA est appelée pour formater une solution finale claire et structurée
    à partir du diagnostic existant. La solution formatée est retournée et
    sauvegardée dans la base de données.

    Ce qui se passe :
    1. Récupérer le document incident depuis MongoDB
    2. Appeler Azure OpenAI avec un prompt de formatage
    3. Stocker la solution finale dans 'validated_solution'
    4. Passer le statut à 'résolu'
    5. Retourner la solution formatée pour affichage immédiat
    """
    incident = await database.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident non trouvé")

    if incident.get("status") == "résolu":
        # Incident déjà résolu : retourner la solution existante
        return {
            "message": "Incident déjà résolu",
            "incident_id": incident_id,
            "formatted_solution": incident.get("validated_solution", ""),
            "already_resolved": True,
        }

    logger.info(f"✅ Approbation de l'incident {incident_id} — formatage de la solution finale via IA")

    # Appeler l'IA pour formater la solution finale
    formatted_solution = await llm_engine.format_final_solution(incident)

    # Sauvegarder la solution validée et passer le statut à résolu
    await database.update_incident_status(
        incident_id=incident_id,
        status="résolu",
        validated_solution=formatted_solution,
    )

    logger.info(f"💾 Incident {incident_id} → statut 'résolu', solution finale sauvegardée")

    return {
        "message": "Incident approuvé et résolu",
        "incident_id": incident_id,
        "formatted_solution": formatted_solution,
        "already_resolved": False,
    }


@router.put("/incidents/{incident_id}/resolve", tags=["Incidents"])
async def resolve_incident(incident_id: str, body: ValidateRequest) -> dict[str, str]:
    """
    (Endpoint de compatibilité) Résolution manuelle d'un incident avec une solution textuelle.

    Utilisé si le SRE souhaite fournir sa propre solution sans passer par le formatage IA.
    Préférer le endpoint POST /incidents/{id}/approve pour le flux standard.
    """
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
        f"✅ Incident {incident_id} résolu manuellement — "
        f"solution: {body.validated_solution[:80]}..."
    )

    return {
        "message": "Incident marqué comme résolu",
        "incident_id": incident_id,
        "validated_solution": body.validated_solution,
    }
