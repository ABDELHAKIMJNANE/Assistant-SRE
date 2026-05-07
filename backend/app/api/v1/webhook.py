"""Webhook endpoint — Reçoit les alertes Grafana et lance la pipeline IA."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks

from app.dependencies.investigation import InvestigationPipelineDependency
from app.graph_pipeline import InvestigationPipeline
from app.models.webhook import AlertPayload
from app.services import database, notification

logger = logging.getLogger(__name__)
router = APIRouter()


async def process_alert(
    payload: AlertPayload,
    investigation_pipeline: InvestigationPipeline,
) -> None:
    """
    Pipeline complète de traitement d'une alerte.
    Exécutée en arrière-plan pour répondre immédiatement à Grafana.

    Étapes :
    1. Auto-Learning : chercher un incident résolu passé (Cosmos DB)
    2. Exécuter la pipeline LangGraph (window, logs/metrics, filtrage+redaction, diagnostic, solution)
    3. Sauvegarder l'incident dans Cosmos DB
    4. Envoyer un email de notification via Outlook
    """
    pod = payload.labels.get("pod", "unknown")
    namespace = payload.labels.get("namespace", "app-demo")

    logger.info(f"🔄 Traitement de l'alerte '{payload.alert_name}' — pod={pod}")

    # ── ① Auto-Learning : chercher dans Cosmos DB (0 token) ──
    past_incident = await database.find_past_incident(payload.alert_name)
    past_solution = None
    if past_incident:
        # Utiliser la solution validée par le SRE si disponible
        past_solution = past_incident.get("validated_solution") or past_incident.get("diagnostic", {}).get("solution")

    # ── ② Pipeline LangGraph multi-étapes ──
    investigation_state = await investigation_pipeline.run(payload=payload, past_solution=past_solution)
    diagnostic = investigation_state.diagnostic or {}

    # ── ③ Sauvegarde dans Cosmos DB ──
    # L'incident est créé avec status "pending_approval".
    # La solution validée finale sera enregistrée UNIQUEMENT quand le SRE approuve.
    incident_doc = {
        "alert_name": payload.alert_name,
        "state": payload.state,
        "labels": payload.labels,
        "message": payload.message,
        "logs_collected": len(investigation_state.raw_logs),
        "metrics_collected": len(investigation_state.raw_metrics),
        "past_solution_used": past_solution,
        "diagnostic": diagnostic,
        "incident_window": investigation_state.incident_window.model_dump(mode="json") if investigation_state.incident_window else None,
        "evidence": investigation_state.evidence,
        "redaction_map": investigation_state.redaction_map,
        "confidence_score": investigation_state.confidence_score,
        "solution_steps": investigation_state.solution_steps,
        "status": "pending_approval",
        "validated_solution": None,
        "created_at": datetime.now(timezone.utc),
        "resolved_at": None,
    }
    incident_id = await database.insert_incident(incident_doc)

    # ── ④ Notification Email Outlook ──
    await notification.send_alert_email(
        alert_name=payload.alert_name,
        pod=pod,
        namespace=namespace,
        diagnostic=diagnostic,
    )

    logger.info(f"✅ Incident '{payload.alert_name}' traité et sauvegardé (id={incident_id})")


@router.post("/webhook", status_code=202, tags=["Webhook"])
async def receive_webhook(
    payload: AlertPayload,
    background_tasks: BackgroundTasks,
    investigation_pipeline: InvestigationPipelineDependency,
) -> dict[str, str]:
    """
    Reçoit une alerte Grafana et lance le traitement en arrière-plan.

    Grafana a un timeout court (~5s). L'analyse IA prend 10-20s.
    On répond donc immédiatement 202 Accepted et on traite en background.
    """
    logger.info(f"📥 Webhook reçu : {payload.alert_name} — {payload.state}")
    background_tasks.add_task(process_alert, payload, investigation_pipeline)
    return {"message": "Alerte reçue, traitement en cours"}
