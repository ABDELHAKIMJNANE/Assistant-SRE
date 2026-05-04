"""Webhook endpoint — Reçoit les alertes Grafana et lance la pipeline IA."""

import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks

from app.models.webhook import AlertPayload
from app.services import database, loki_client, prometheus_client, sanitizer, llm_engine, notification

logger = logging.getLogger(__name__)
router = APIRouter()


async def process_alert(payload: AlertPayload):
    """
    Pipeline complète de traitement d'une alerte.
    Exécutée en arrière-plan pour répondre immédiatement à Grafana.

    Étapes :
    1. Collecter les logs (Loki) et métriques (Prometheus)
    2. Auto-Learning : chercher un incident résolu passé (Cosmos DB)
    3. Tronquer et nettoyer les données (Sanitizer)
    4. Construire le Mega-Prompt et appeler Azure OpenAI
    5. Sauvegarder l'incident dans Cosmos DB
    6. Envoyer un email de notification via Outlook
    """
    pod = payload.labels.get("pod", "unknown")
    namespace = payload.labels.get("namespace", "app-demo")

    logger.info(f"🔄 Traitement de l'alerte '{payload.alert_name}' — pod={pod}")

    # ── ① Collecte des Preuves ──
    logs = await loki_client.get_logs(pod=pod, namespace=namespace)
    metrics = await prometheus_client.get_metrics(pod=pod, namespace=namespace)

    # ── ② Auto-Learning : chercher dans Cosmos DB (0 token) ──
    past_incident = await database.find_past_incident(payload.alert_name)
    past_solution = None
    if past_incident:
        # Utiliser la solution validée par le SRE si disponible
        past_solution = past_incident.get("validated_solution") or past_incident.get("diagnostic", {}).get("solution")

    # ── ③ Troncature + ④ Sanitizer ──
    cleaned_logs = sanitizer.sanitize_logs(logs, max_lines=50)

    # ── ⑤ Mega-Prompt Azure OpenAI ──
    diagnostic = await llm_engine.analyze(
        alert_name=payload.alert_name,
        message=payload.message,
        labels=payload.labels,
        cleaned_logs=cleaned_logs,
        metrics=metrics,
        past_solution=past_solution,
    )

    # ── ⑥ Sauvegarde dans Cosmos DB ──
    incident_doc = {
        "alert_name": payload.alert_name,
        "state": payload.state,
        "labels": payload.labels,
        "message": payload.message,
        "logs_collected": len(logs),
        "metrics_collected": len(metrics),
        "past_solution_used": past_solution,
        "diagnostic": diagnostic,
        "status": "ouvert",
        "validated_solution": None,
        "created_at": datetime.utcnow(),
        "resolved_at": None,
    }
    incident_id = await database.insert_incident(incident_doc)

    # ── ⑦ Notification Email Outlook ──
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
):
    """
    Reçoit une alerte Grafana et lance le traitement en arrière-plan.

    Grafana a un timeout court (~5s). L'analyse IA prend 10-20s.
    On répond donc immédiatement 202 Accepted et on traite en background.
    """
    logger.info(f"📥 Webhook reçu : {payload.alert_name} — {payload.state}")
    background_tasks.add_task(process_alert, payload)
    return {"message": "Alerte reçue, traitement en cours"}
