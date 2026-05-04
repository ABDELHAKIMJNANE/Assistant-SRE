"""Fixtures pytest pour les tests du backend AIOps."""

import asyncio
from unittest.mock import AsyncMock, patch

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
    Client de test FastAPI avec MongoDB mocké.
    Aucune connexion réelle à MongoDB ou OpenAI nécessaire.
    """
    with patch("app.services.database.connect_db", new_callable=AsyncMock):
        with patch("app.services.database.close_db", new_callable=AsyncMock):
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
