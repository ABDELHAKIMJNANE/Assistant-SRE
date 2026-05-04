"""LLMEngine — Construction du Mega-Prompt et appel Azure OpenAI."""

import json
import logging
from typing import Optional

from openai import AsyncAzureOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

# ── Client Azure OpenAI (initialisé au premier appel) ──
_openai_client: Optional[AsyncAzureOpenAI] = None


def _get_client() -> AsyncAzureOpenAI:
    """Initialiser le client Azure OpenAI (lazy)."""
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncAzureOpenAI(
            azure_endpoint=settings.openai_endpoint,
            api_key=settings.openai_api_key,
            api_version=settings.openai_api_version,
        )
    return _openai_client


SYSTEM_PROMPT = """Tu es un expert SRE (Site Reliability Engineer) spécialisé en Kubernetes.
Tu reçois des alertes de monitoring avec des logs et métriques.
Tu dois fournir un diagnostic structuré en JSON avec les champs suivants :
- cause_racine : Explication claire de la cause du problème
- solution : Commande ou action exacte pour résoudre le problème
- severite : "critique", "haute", "moyenne", ou "basse"
- categorie : Type de problème (ex: "resource_exhaustion", "network_error", "crash_loop", "configuration_error")

Réponds UNIQUEMENT avec du JSON valide, sans texte autour."""


async def analyze(
    alert_name: str,
    message: str,
    labels: dict,
    cleaned_logs: list[str],
    metrics: dict,
    past_solution: Optional[str] = None,
) -> dict:
    """
    Construire le Mega-Prompt et appeler Azure OpenAI.

    Args:
        alert_name: Nom de l'alerte (ex: "OOMKilled")
        message: Message de l'alerte
        labels: Labels K8s (pod, namespace, container)
        cleaned_logs: Logs nettoyés par le Sanitizer
        metrics: Métriques du pod
        past_solution: Solution passée trouvée par l'Auto-Learning (ou None)

    Returns:
        Dict avec cause_racine, solution, severite, categorie
    """
    # ── Construction du Mega-Prompt ──
    logs_text = "\n".join(cleaned_logs) if cleaned_logs else "Aucun log disponible"

    mem_mi = metrics.get("memory_usage_bytes", 0) / (1024 * 1024)
    metrics_text = (
        f"- Mémoire : {mem_mi:.1f} Mi\n"
        f"- CPU cumulé : {metrics.get('cpu_usage_seconds', 0):.1f}s\n"
        f"- Restarts : {int(metrics.get('restart_count', 0))}"
    )

    user_prompt = f"""## Alerte Kubernetes
- Nom : {alert_name}
- Message : {message}
- Pod : {labels.get('pod', 'inconnu')}
- Namespace : {labels.get('namespace', 'inconnu')}
- Container : {labels.get('container', 'inconnu')}

## Logs (dernières {len(cleaned_logs)} lignes)
{logs_text}

## Métriques
{metrics_text}
"""

    # Ajouter la solution passée si l'Auto-Learning en a trouvé une
    if past_solution:
        user_prompt += f"""
## Historique Auto-Learning
La dernière fois que cette alerte '{alert_name}' est survenue, la solution validée était :
"{past_solution}"
Tiens compte de cette solution passée dans ton diagnostic.
"""

    logger.info(
        f"📤 Mega-Prompt envoyé à OpenAI "
        f"{'AVEC' if past_solution else 'SANS'} historique "
        f"({len(cleaned_logs)} logs, {len(metrics)} métriques)"
    )

    try:
        client = _get_client()
        response = await client.chat.completions.create(
            model=settings.openai_deployment,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=800,
        )

        raw_content = response.choices[0].message.content.strip()

        # Parser la réponse JSON
        # Gérer le cas où l'IA entoure le JSON de ```json ... ```
        if raw_content.startswith("```"):
            raw_content = raw_content.split("```")[1]
            if raw_content.startswith("json"):
                raw_content = raw_content[4:]

        diagnostic = json.loads(raw_content)
        logger.info(f"✅ Diagnostic IA reçu — sévérité: {diagnostic.get('severite', '?')}")
        return diagnostic

    except json.JSONDecodeError:
        logger.error(f"❌ Réponse OpenAI non-JSON : {raw_content[:200]}")
        return {
            "cause_racine": raw_content[:500],
            "solution": "Analyse manuelle requise",
            "severite": "moyenne",
            "categorie": "parse_error",
        }
    except Exception as e:
        logger.error(f"❌ Erreur OpenAI : {e}")
        return {
            "cause_racine": f"Erreur lors de l'appel OpenAI : {str(e)}",
            "solution": "Vérifier la clé API et le déploiement OpenAI",
            "severite": "haute",
            "categorie": "api_error",
        }


async def chat_about_incident(incident: dict, question: str) -> str:
    """
    Chatbot SRE : poser une question contextuelle sur un incident.
    Re-prompt OpenAI avec le contexte complet de l'incident.
    """
    diagnostic = incident.get("diagnostic", {})

    user_prompt = f"""## Contexte de l'incident
- Alerte : {incident.get('alert_name', '?')}
- Message : {incident.get('message', '?')}
- Cause racine identifiée : {diagnostic.get('cause_racine', '?')}
- Solution proposée : {diagnostic.get('solution', '?')}
- Sévérité : {diagnostic.get('severite', '?')}
- Status : {incident.get('status', '?')}

## Question de l'ingénieur SRE
{question}

Réponds de manière claire et concise. Si tu donnes des commandes, donne-les exactes et prêtes à copier."""

    try:
        client = _get_client()
        response = await client.chat.completions.create(
            model=settings.openai_deployment,
            messages=[
                {"role": "system", "content": "Tu es un expert SRE Kubernetes. Réponds aux questions de l'ingénieur de manière précise et actionnable."},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            max_tokens=600,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"❌ Erreur chat OpenAI : {e}")
        return f"Erreur lors de la communication avec l'IA : {str(e)}"
