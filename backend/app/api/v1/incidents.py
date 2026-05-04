"""Incidents endpoints — Liste et détail des incidents."""

import logging

from fastapi import APIRouter, HTTPException, Query

from app.services import database, loki_client, prometheus_client

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/incidents", tags=["Incidents"])
async def list_incidents(
    skip: int = Query(0, ge=0, description="Nombre d'incidents à sauter"),
    limit: int = Query(20, ge=1, le=100, description="Nombre d'incidents à retourner"),
):
    """
    Liste paginée de tous les incidents, du plus récent au plus ancien.
    Utilisé par Streamlit pour afficher l'index des incidents.
    """
    incidents = await database.list_incidents(skip=skip, limit=limit)
    return incidents


@router.get("/incidents/{incident_id}", tags=["Incidents"])
async def get_incident_detail(incident_id: str):
    """
    Détail complet d'un incident avec re-fetch des logs et métriques.
    Quand le SRE clique sur un incident dans Streamlit, on récupère :
    - Le document incident depuis Cosmos DB
    - Les logs actuels du pod depuis Loki
    - Les métriques actuelles du pod depuis Prometheus
    """
    incident = await database.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident non trouvé")

    # Re-fetch logs et métriques pour affichage en temps réel
    pod = incident.get("labels", {}).get("pod", "")
    namespace = incident.get("labels", {}).get("namespace", "app-demo")

    logs = []
    metrics = {}
    if pod:
        logs = await loki_client.get_logs(pod=pod, namespace=namespace, limit=50)
        metrics = await prometheus_client.get_metrics(pod=pod, namespace=namespace)

    incident["current_logs"] = logs
    incident["current_metrics"] = metrics

    return incident
