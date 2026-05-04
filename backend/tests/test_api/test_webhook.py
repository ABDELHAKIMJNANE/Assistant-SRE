"""Tests du endpoint POST /api/v1/webhook."""
from unittest.mock import AsyncMock, patch
import pytest


class TestWebhookEndpoint:
    """Tests du POST /api/v1/webhook."""

    def test_webhook_returns_202(self, client, sample_webhook_payload):
        """Le webhook doit répondre 202 immédiatement."""
        response = client.post("/api/v1/webhook", json=sample_webhook_payload)
        assert response.status_code == 202
        assert "traitement en cours" in response.json()["message"].lower()

    def test_webhook_invalid_payload_missing_alert_name(self, client):
        """Un payload sans alert_name doit retourner 422."""
        response = client.post("/api/v1/webhook", json={})
        assert response.status_code == 422

    def test_webhook_minimal_payload(self, client):
        """Un payload avec seulement alert_name doit être accepté."""
        response = client.post("/api/v1/webhook", json={"alert_name": "TestAlert"})
        assert response.status_code == 202

    def test_webhook_with_dashboard_url(self, client, sample_webhook_payload):
        """Payload avec dashboard_url optionnel."""
        payload = {**sample_webhook_payload, "dashboard_url": "https://grafana.example.com/d/abc"}
        response = client.post("/api/v1/webhook", json=payload)
        assert response.status_code == 202

    def test_webhook_response_structure(self, client, sample_webhook_payload):
        """La réponse doit avoir la structure attendue."""
        response = client.post("/api/v1/webhook", json=sample_webhook_payload)
        data = response.json()
        assert "message" in data
