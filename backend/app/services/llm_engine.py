"""LLMEngine — Construction du Mega-Prompt et appel Azure OpenAI."""

import json
import logging
from collections import Counter
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


SYSTEM_PROMPT = """Tu es un expert SRE (Site Reliability Engineer) spécialisé en Kubernetes et observabilité.
Tu reçois des alertes de monitoring Grafana avec des logs applicatifs et des métriques système.

Ton rôle : analyser les preuves collectées et produire un diagnostic exploitable.

Réponds UNIQUEMENT avec un objet JSON valide ayant exactement ces champs :
{
  "cause_racine": "Explication technique précise de la cause du problème (2-4 phrases)",
  "solution": "Commandes exactes et étapes pour résoudre le problème (prêtes à copier-coller)",
  "severite": "critique | haute | moyenne | basse",
  "categorie": "resource_exhaustion | memory_leak | crash_loop | network_error | disk_full | high_latency | configuration_error | unknown",
  "actions_immediates": ["action 1", "action 2", "action 3"],
  "prevention": "Recommandation pour éviter la récurrence"
}

Règles importantes :
- Ne jamais inclure de texte en dehors du JSON
- La solution doit contenir des commandes kubectl/bash concrètes et exécutables
- Les actions immédiates doivent être ordonnées par priorité
- Tenir compte des logs ET des métriques pour le diagnostic"""


def _analyze_logs(logs: list[str]) -> dict:
    """Analyser les logs pour extraire des informations utiles pour le prompt."""
    if not logs:
        return {
            "error_count": 0,
            "warn_count": 0,
            "info_count": 0,
            "recent_errors": [],
            "recent_warnings": [],
        }

    severity_counts: Counter = Counter()
    errors: list[str] = []
    warnings: list[str] = []

    for line in logs:
        line_lower = line.lower()
        if any(k in line_lower for k in ("error", "err", "exception", "fatal", "critical", "oomkilled", "oom")):
            severity_counts["ERROR"] += 1
            errors.append(line[-200:])  # garder les 200 derniers caractères
        elif any(k in line_lower for k in ("warn", "warning")):
            severity_counts["WARN"] += 1
            warnings.append(line[-200:])
        elif any(k in line_lower for k in ("info",)):
            severity_counts["INFO"] += 1

    return {
        "error_count": severity_counts["ERROR"],
        "warn_count": severity_counts["WARN"],
        "info_count": severity_counts["INFO"],
        "recent_errors": errors[-5:],   # 5 dernières erreurs
        "recent_warnings": warnings[-3:],  # 3 derniers warnings
    }


def _format_metrics_context(metrics: dict) -> str:
    """Formater les métriques avec contexte et seuils d'alerte."""
    if not metrics:
        return "Aucune métrique disponible"

    mem_bytes = metrics.get("memory_usage_bytes", 0)
    mem_mi = mem_bytes / (1024 * 1024)
    mem_limit_mi = metrics.get("memory_limit_bytes", 0) / (1024 * 1024) if metrics.get("memory_limit_bytes") else None
    cpu_seconds = metrics.get("cpu_usage_seconds", 0)
    restarts = int(metrics.get("restart_count", 0))
    cpu_throttled = metrics.get("cpu_throttled_seconds", 0)
    network_rx = metrics.get("network_receive_bytes", 0)
    network_tx = metrics.get("network_transmit_bytes", 0)

    lines = [
        f"- Mémoire utilisée    : {mem_mi:.1f} Mi"
        + (f" / {mem_limit_mi:.1f} Mi limit ({mem_mi/mem_limit_mi*100:.0f}%)" if mem_limit_mi else ""),
        f"- CPU cumulé          : {cpu_seconds:.1f}s",
        f"- CPU throttled       : {cpu_throttled:.1f}s",
        f"- Redémarrages        : {restarts}" + (" ⚠️ CRASH LOOP" if restarts >= 5 else ""),
        f"- Réseau RX/TX        : {network_rx/(1024*1024):.1f} Mi / {network_tx/(1024*1024):.1f} Mi",
    ]

    # Ajouter des indicateurs de dépassement de seuils
    if mem_limit_mi and mem_mi / mem_limit_mi > 0.85:
        lines.append(f"🔴 ALERTE : Mémoire à {mem_mi/mem_limit_mi*100:.0f}% de la limite — risque OOMKilled")
    if restarts >= 3:
        lines.append(f"🔴 ALERTE : {restarts} redémarrages — potentiel crash loop")

    return "\n".join(lines)


async def analyze(
    alert_name: str,
    message: str,
    labels: dict,
    cleaned_logs: list[str],
    metrics: dict,
    past_solution: Optional[str] = None,
) -> dict:
    """
    Construire le Mega-Prompt enrichi et appeler Azure OpenAI.

    Args:
        alert_name: Nom de l'alerte (ex: "OOMKilled")
        message: Message de l'alerte
        labels: Labels K8s (pod, namespace, container)
        cleaned_logs: Logs nettoyés par le Sanitizer
        metrics: Métriques du pod
        past_solution: Solution passée trouvée par l'Auto-Learning (ou None)

    Returns:
        Dict avec cause_racine, solution, severite, categorie, actions_immediates, prevention
    """
    log_analysis = _analyze_logs(cleaned_logs)
    metrics_context = _format_metrics_context(metrics)

    logs_full = "\n".join(cleaned_logs) if cleaned_logs else "Aucun log disponible"

    # Résumé des erreurs et warnings extraits
    error_summary = ""
    if log_analysis["recent_errors"]:
        error_summary = "\n### Erreurs récentes détectées dans les logs\n"
        for err in log_analysis["recent_errors"]:
            error_summary += f"  ❌ {err}\n"
    if log_analysis["recent_warnings"]:
        error_summary += "\n### Warnings récents\n"
        for warn in log_analysis["recent_warnings"]:
            error_summary += f"  ⚠️ {warn}\n"

    user_prompt = f"""## Alerte Kubernetes reçue de Grafana
- Nom de l'alerte : {alert_name}
- Message         : {message}
- Pod             : {labels.get('pod', 'inconnu')}
- Namespace       : {labels.get('namespace', 'inconnu')}
- Container       : {labels.get('container', 'inconnu')}
- Node            : {labels.get('node', 'inconnu')}

## Statistiques des logs ({len(cleaned_logs)} lignes collectées)
- Erreurs   : {log_analysis['error_count']}
- Warnings  : {log_analysis['warn_count']}
- Info      : {log_analysis['info_count']}
{error_summary}
## Logs complets (triés du plus ancien au plus récent)
```
{logs_full}
```

## Métriques système
{metrics_context}
"""

    if past_solution:
        user_prompt += f"""
## Contexte Auto-Learning (incident similaire passé)
Une occurrence précédente de '{alert_name}' a été résolue avec la solution validée par l'ingénieur SRE :
> {past_solution}
Tiens compte de cette solution éprouvée dans ton analyse.
"""

    logger.info(
        f"📤 Mega-Prompt envoyé à OpenAI "
        f"({'AVEC' if past_solution else 'SANS'} historique) — "
        f"{len(cleaned_logs)} logs, {log_analysis['error_count']} erreurs, {len(metrics)} métriques"
    )

    try:
        client = _get_client()
        response = await client.chat.completions.create(
            model=settings.openai_deployment,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=1200,
        )

        raw_content = response.choices[0].message.content.strip()

        # Gérer le cas où l'IA entoure le JSON de ```json ... ```
        if raw_content.startswith("```"):
            parts = raw_content.split("```")
            raw_content = parts[1]
            if raw_content.startswith("json"):
                raw_content = raw_content[4:]

        diagnostic = json.loads(raw_content)

        # Assurer la compatibilité avec les champs attendus par le reste du code
        if "actions_immediates" not in diagnostic:
            diagnostic["actions_immediates"] = []
        if "prevention" not in diagnostic:
            diagnostic["prevention"] = ""

        logger.info(f"✅ Diagnostic IA reçu — sévérité: {diagnostic.get('severite', '?')}, catégorie: {diagnostic.get('categorie', '?')}")
        return diagnostic

    except json.JSONDecodeError:
        logger.error(f"❌ Réponse OpenAI non-JSON : {raw_content[:200]}")
        return {
            "cause_racine": raw_content[:500],
            "solution": "Analyse manuelle requise",
            "severite": "moyenne",
            "categorie": "parse_error",
            "actions_immediates": [],
            "prevention": "",
        }
    except Exception as e:
        logger.error(f"❌ Erreur OpenAI : {e}")
        return {
            "cause_racine": f"Erreur lors de l'appel OpenAI : {str(e)}",
            "solution": "Vérifier la clé API et le déploiement OpenAI",
            "severite": "haute",
            "categorie": "api_error",
            "actions_immediates": [],
            "prevention": "",
        }


async def format_final_solution(incident: dict) -> str:
    """
    Formater la solution finale validée par l'ingénieur SRE.
    Appelé après que le SRE clique sur 'Approuver' pour obtenir une solution
    bien structurée, claire et directement utilisable.

    Args:
        incident: Document complet de l'incident depuis MongoDB

    Returns:
        Solution finale formatée en markdown, prête à être sauvegardée et affichée
    """
    diagnostic = incident.get("diagnostic", {})

    system_prompt = (
        "Tu es un expert SRE. Ton rôle est de produire un rapport de résolution d'incident "
        "clair, structuré et directement utilisable par un ingénieur SRE."
    )

    user_prompt = f"""L'ingénieur SRE a approuvé la résolution de l'incident suivant.
Produis un rapport de résolution final, bien structuré, en français.

## Incident
- Alerte     : {incident.get('alert_name', '?')}
- Pod        : {incident.get('labels', {}).get('pod', '?')}
- Namespace  : {incident.get('labels', {}).get('namespace', '?')}
- Message    : {incident.get('message', '?')}

## Diagnostic IA initial
- Cause racine    : {diagnostic.get('cause_racine', '?')}
- Solution initiale: {diagnostic.get('solution', '?')}
- Sévérité        : {diagnostic.get('severite', '?')}
- Catégorie       : {diagnostic.get('categorie', '?')}
- Actions immédiates : {', '.join(diagnostic.get('actions_immediates', []))}
- Prévention      : {diagnostic.get('prevention', '?')}

## Format attendu (markdown)
Produis exactement ce format :

### ✅ Résolution de l'incident : {incident.get('alert_name', '?')}

**Cause identifiée :** [explication claire en 1-2 phrases]

**Commandes de résolution :**
```bash
[commandes exactes, une par ligne]
```

**Étapes de vérification :**
1. [étape 1]
2. [étape 2]
3. [étape 3]

**Prévention future :**
[recommandation concrète]

Réponds uniquement avec le markdown, sans texte supplémentaire."""

    try:
        client = _get_client()
        response = await client.chat.completions.create(
            model=settings.openai_deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=800,
        )
        formatted = response.choices[0].message.content.strip()
        logger.info(f"✅ Solution finale formatée pour l'incident {incident.get('_id', '?')}")
        return formatted

    except Exception as e:
        logger.error(f"❌ Erreur formatage solution finale : {e}")
        # Fallback : retourner la solution brute du diagnostic
        return diagnostic.get("solution", "Solution non disponible")


async def chat_about_incident(incident: dict, question: str) -> str:
    """
    Chatbot SRE : poser une question contextuelle sur un incident.
    Re-prompt OpenAI avec le contexte complet de l'incident.
    """
    diagnostic = incident.get("diagnostic", {})

    user_prompt = f"""## Contexte de l'incident
- Alerte              : {incident.get('alert_name', '?')}
- Pod/Namespace       : {incident.get('labels', {}).get('pod', '?')} / {incident.get('labels', {}).get('namespace', '?')}
- Message             : {incident.get('message', '?')}
- Cause racine        : {diagnostic.get('cause_racine', '?')}
- Solution proposée   : {diagnostic.get('solution', '?')}
- Sévérité            : {diagnostic.get('severite', '?')}
- Catégorie           : {diagnostic.get('categorie', '?')}
- Actions immédiates  : {', '.join(diagnostic.get('actions_immediates', []))}
- Status actuel       : {incident.get('status', '?')}

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
            max_tokens=700,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"❌ Erreur chat OpenAI : {e}")
        return f"Erreur lors de la communication avec l'IA : {str(e)}"
