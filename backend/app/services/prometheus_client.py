"""PrometheusClient — Récupère les métriques depuis Prometheus via PromQL (async)."""

import logging
from datetime import datetime

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def get_metrics(
    pod: str,
    namespace: str = "app-demo",
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict[str, float]:
    """
    Interroger Prometheus pour récupérer les métriques d'un pod.
    Récupère : CPU, Mémoire, Restarts.

    Args:
        pod: Nom du pod Kubernetes
        namespace: Namespace du pod

    Returns:
        Dict avec les métriques clés du pod
    """
    base_url = f"{settings.prometheus_url}/api/v1/query"
    if start and end:
        base_url = f"{settings.prometheus_url}/api/v1/query_range"
    metrics = {}

    queries = {
        "memory_usage_bytes": f'container_memory_usage_bytes{{pod="{pod}",namespace="{namespace}"}}',
        "cpu_usage_seconds": f'container_cpu_usage_seconds_total{{pod="{pod}",namespace="{namespace}"}}',
        "restart_count": f'kube_pod_container_status_restarts_total{{pod="{pod}",namespace="{namespace}"}}',
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            for metric_name, query in queries.items():
                params: dict[str, str | float] = {"query": query}
                if start and end:
                    params.update(
                        {
                            "start": start.timestamp(),
                            "end": end.timestamp(),
                            "step": "30s",
                        }
                    )
                response = await client.get(base_url, params=params)
                response.raise_for_status()

                data = response.json()
                results = data.get("data", {}).get("result", [])

                if results:
                    if start and end:
                        range_values = results[0].get("values", [])
                        value = range_values[-1][1] if range_values else "0"
                    else:
                        value = results[0].get("value", [None, "0"])[1]
                    metrics[metric_name] = float(value)
                else:
                    metrics[metric_name] = 0.0

        logger.info(f"📊 Métriques récupérées pour pod={pod} : {metrics}")
        return metrics

    except httpx.HTTPError as e:
        logger.warning(f"⚠️ Erreur Prometheus : {e} — retour métriques vides")
        return {"memory_usage_bytes": 0, "cpu_usage_seconds": 0, "restart_count": 0}
    except Exception as e:
        logger.error(f"❌ Erreur inattendue Prometheus : {e}")
        return {"memory_usage_bytes": 0, "cpu_usage_seconds": 0, "restart_count": 0}


def format_metrics_for_prompt(metrics: dict[str, float]) -> str:
    """Formater les métriques pour les inclure dans le Mega-Prompt OpenAI."""
    mem_mi = metrics.get("memory_usage_bytes", 0) / (1024 * 1024)
    cpu = metrics.get("cpu_usage_seconds", 0)
    restarts = int(metrics.get("restart_count", 0))

    return (
        f"- Mémoire utilisée : {mem_mi:.1f} Mi\n"
        f"- CPU cumulé : {cpu:.1f} secondes\n"
        f"- Nombre de restarts : {restarts}"
    )
