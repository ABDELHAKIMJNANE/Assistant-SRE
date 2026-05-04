"""LokiClient — Récupère les logs depuis Loki via LogQL (async)."""

import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def get_logs(
    pod: str,
    namespace: str = "app-demo",
    limit: int = 100,
    since: str = "30m",
) -> list[str]:
    """
    Interroger Loki pour récupérer les logs d'un pod spécifique.
    Utilise l'API query_range de Loki avec une requête LogQL.

    Args:
        pod: Nom du pod Kubernetes
        namespace: Namespace du pod
        limit: Nombre max de lignes de logs
        since: Période de temps (ex: '30m', '1h')

    Returns:
        Liste de lignes de logs (strings)
    """
    query = f'{{namespace="{namespace}", pod="{pod}"}}'
    url = f"{settings.loki_url}/loki/api/v1/query_range"

    params = {
        "query": query,
        "limit": limit,
        "since": since,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()

        data = response.json()
        logs = []

        # Extraire les lignes de logs depuis la réponse Loki
        results = data.get("data", {}).get("result", [])
        for stream in results:
            for _timestamp, line in stream.get("values", []):
                logs.append(line)

        logger.info(f"📝 {len(logs)} logs récupérés depuis Loki pour pod={pod}")
        return logs

    except httpx.HTTPError as e:
        logger.warning(f"⚠️ Erreur Loki : {e} — retour liste vide")
        return []
    except Exception as e:
        logger.error(f"❌ Erreur inattendue Loki : {e}")
        return []
