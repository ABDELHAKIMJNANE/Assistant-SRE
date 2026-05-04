"""Tests du endpoint webhook."""

import pytest


class TestWebhookEndpoint:
    """Tests du POST /api/v1/webhook."""

    def test_webhook_returns_202(self, client, sample_webhook_payload):
        """Le webhook doit répondre 202 immédiatement."""
        response = client.post("/api/v1/webhook", json=sample_webhook_payload)
        assert response.status_code == 202
        assert "traitement en cours" in response.json()["message"].lower()

    def test_webhook_invalid_payload(self, client):
        """Un payload invalide doit retourner 422."""
        response = client.post("/api/v1/webhook", json={})
        assert response.status_code == 422

    def test_webhook_minimal_payload(self, client):
        """Un payload avec seulement alert_name doit être accepté."""
        response = client.post("/api/v1/webhook", json={"alert_name": "TestAlert"})
        assert response.status_code == 202


class TestHealthCheck:
    """Tests du GET /healthz."""

    def test_health_check(self, client):
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
