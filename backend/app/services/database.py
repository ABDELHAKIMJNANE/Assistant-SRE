"""CosmosDBClient — Client MongoDB async (motor) pour FIND / INSERT / UPDATE."""

import logging
from datetime import datetime
from typing import Any, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import settings

logger = logging.getLogger(__name__)

_client: Optional[AsyncIOMotorClient] = None


async def connect_db() -> None:
    """Ouvrir la connexion MongoDB au démarrage de l'application."""
    global _client
    _client = AsyncIOMotorClient(settings.mongodb_url)
    # Ping pour vérifier la connexion
    await _client.admin.command("ping")
    logger.info(f"✅ MongoDB connecté : {settings.mongodb_url[:30]}...")


async def close_db() -> None:
    """Fermer la connexion MongoDB à l'arrêt."""
    global _client
    if _client:
        _client.close()
        logger.info("🛑 MongoDB déconnecté")


def get_db() -> AsyncIOMotorDatabase:
    """Retourner la base de données configurée."""
    return _client[settings.mongodb_db_name]


# ═══════════════════════════════════════════════
# Opérations CRUD sur la collection 'incidents'
# ═══════════════════════════════════════════════


async def find_past_incident(alert_name: str) -> Optional[dict[str, Any]]:
    """
    Auto-Learning : chercher un incident RÉSOLU passé pour la même alerte.
    Retourne la solution validée la plus récente, ou None.
    Coût : 0 token OpenAI (simple requête DB).
    """
    db = get_db()
    doc = await db["incidents"].find_one(
        {"alert_name": alert_name, "status": "résolu"},
        sort=[("created_at", -1)],
    )
    if doc:
        doc["_id"] = str(doc["_id"])
        logger.info(f"🔄 Incident passé trouvé pour '{alert_name}' — solution: {doc.get('validated_solution', 'N/A')[:80]}")
    else:
        logger.info(f"❌ Aucun incident passé résolu pour '{alert_name}'")
    return doc


async def insert_incident(doc: dict[str, Any]) -> str:
    """
    Sauvegarder un nouvel incident dans MongoDB / Cosmos DB.
    Retourne l'ID du document inséré.
    """
    db = get_db()
    result = await db["incidents"].insert_one(doc)
    incident_id = str(result.inserted_id)
    logger.info(f"💾 Incident sauvegardé : {incident_id}")
    return incident_id


async def get_incident(incident_id: str) -> Optional[dict[str, Any]]:
    """Récupérer un incident par son ID."""
    db = get_db()
    doc = await db["incidents"].find_one({"_id": ObjectId(incident_id)})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


async def list_incidents(skip: int = 0, limit: int = 20) -> list[dict[str, Any]]:
    """Liste paginée de tous les incidents, du plus récent au plus ancien."""
    db = get_db()
    cursor = (
        db["incidents"]
        .find({})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    incidents = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        incidents.append(doc)
    return incidents


async def update_incident_status(
    incident_id: str,
    status: str,
    validated_solution: Optional[str] = None,
) -> None:
    """
    Mettre à jour le statut d'un incident.
    Quand le SRE clique sur 'Valider', on stocke :
    - status = 'résolu'
    - validated_solution = la solution finale confirmée par le SRE
    - resolved_at = date de résolution
    Cette solution validée sera utilisée par l'Auto-Learning.
    """
    db = get_db()
    update_fields = {"status": status}

    if status == "résolu":
        update_fields["resolved_at"] = datetime.utcnow()

    if validated_solution:
        update_fields["validated_solution"] = validated_solution

    await db["incidents"].update_one(
        {"_id": ObjectId(incident_id)},
        {"$set": update_fields},
    )
    logger.info(f"✅ Incident {incident_id} → status='{status}'")
