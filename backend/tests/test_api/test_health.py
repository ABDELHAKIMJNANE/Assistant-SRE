"""Tests des endpoints health check."""
import pytest


class TestHealthEndpoints:
    """Tests des endpoints /healthz et /api/v1/health/*."""

    def test_healthz(self, client):
        """GET /healthz doit retourner 200."""
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_liveness(self, client):
        """GET /api/v1/health/live doit retourner 200."""
        response = client.get("/api/v1/health/live")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
        assert "service" in data

    def test_startup(self, client):
        """GET /api/v1/health/startup doit retourner 200."""
        response = client.get("/api/v1/health/startup")
        assert response.status_code == 200
        assert response.json()["status"] == "started"
