"""Fixtures pytest pour les tests du backend AIOps."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def event_loop():
    """Créer un event loop pour les tests async."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture()
def client():
    """
    Client de test FastAPI avec MongoDB et services externes mockés.
    Aucune connexion réelle à MongoDB ou OpenAI nécessaire.
    """
    mock_collection = MagicMock()
    mock_collection.find_one = AsyncMock(return_value=None)
    mock_collection.insert_one = AsyncMock(return_value=MagicMock(inserted_id="mock_id"))
    mock_collection.update_one = AsyncMock(return_value=None)

    async def async_empty_cursor(*args, **kwargs):
        return
        yield

    mock_cursor = MagicMock()
    mock_cursor.sort = MagicMock(return_value=mock_cursor)
    mock_cursor.skip = MagicMock(return_value=mock_cursor)
    mock_cursor.limit = MagicMock(return_value=mock_cursor)
    mock_cursor.__aiter__ = lambda self: async_empty_cursor()
    mock_collection.find = MagicMock(return_value=mock_cursor)

    mock_db_instance = MagicMock()
    mock_db_instance.command = AsyncMock(return_value={"ok": 1})
    mock_db_instance.__getitem__ = MagicMock(return_value=mock_collection)

    with patch("app.services.database.connect_db", new_callable=AsyncMock), \
         patch("app.services.database.close_db", new_callable=AsyncMock), \
         patch("app.services.database._client", MagicMock()), \
         patch("app.services.database.get_db", return_value=mock_db_instance):
        from app.main import app
        with TestClient(app) as c:
            yield c


@pytest.fixture()
def mock_db():
    """Mock de toutes les opérations database."""
    with patch("app.api.v1.webhook.database") as mock:
        mock.find_past_incident = AsyncMock(return_value=None)
        mock.insert_incident = AsyncMock(return_value="mock_incident_id")
        yield mock


@pytest.fixture()
def mock_openai():
    """Mock du service LLM Engine."""
    with patch("app.api.v1.webhook.llm_engine") as mock:
        mock.analyze = AsyncMock(return_value={
            "cause_racine": "Memory leak dans /api/data",
            "solution": "kubectl set resources deployment/fastapi-demo --limits=memory=512Mi",
            "severite": "haute",
            "categorie": "resource_exhaustion",
        })
        yield mock


@pytest.fixture()
def mock_loki():
    """Mock du service Loki."""
    with patch("app.api.v1.webhook.loki_client") as mock:
        mock.get_logs = AsyncMock(return_value=[
            "ERROR: Container killed - OOM",
            "WARNING: Memory usage at 98%",
        ])
        yield mock


@pytest.fixture()
def mock_prometheus():
    """Mock du service Prometheus."""
    with patch("app.api.v1.webhook.prometheus_client") as mock:
        mock.get_metrics = AsyncMock(return_value={
            "memory_usage_bytes": 268435456,
            "cpu_usage_seconds": 42.5,
            "restart_count": 3,
        })
        yield mock


@pytest.fixture()
def mock_notification():
    """Mock du service de notification email."""
    with patch("app.api.v1.webhook.notification") as mock:
        mock.send_alert_email = AsyncMock()
        yield mock


@pytest.fixture()
def sample_webhook_payload():
    """Payload webhook Grafana de test."""
    return {
        "alert_name": "OOMKilled",
        "state": "alerting",
        "labels": {
            "pod": "fastapi-demo-7b9c8d6f4-x2k9p",
            "namespace": "app-demo",
            "container": "fastapi",
        },
        "message": "Container killed due to OOM",
    }


@pytest.fixture()
def sample_incident():
    """Incident de test complet."""
    return {
        "_id": "507f1f77bcf86cd799439011",
        "alert_name": "OOMKilled",
        "state": "alerting",
        "labels": {"pod": "fastapi-demo-xxx", "namespace": "app-demo"},
        "message": "Container killed due to OOM",
        "logs_collected": 10,
        "metrics_collected": 3,
        "past_solution_used": None,
        "diagnostic": {
            "cause_racine": "Memory leak",
            "solution": "kubectl set resources ...",
            "severite": "haute",
            "categorie": "resource_exhaustion",
        },
        "status": "ouvert",
        "validated_solution": None,
        "created_at": "2024-01-01T00:00:00",
        "resolved_at": None,
    }
