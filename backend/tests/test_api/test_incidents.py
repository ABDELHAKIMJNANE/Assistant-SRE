"""Tests des endpoints incidents."""
from unittest.mock import AsyncMock, patch
import pytest


class TestListIncidents:
    """Tests du GET /api/v1/incidents."""

    def test_list_incidents_returns_200(self, client):
        """Doit retourner 200 avec une liste."""
        with patch("app.api.v1.incidents.database") as mock_db:
            mock_db.list_incidents = AsyncMock(return_value=[])
            response = client.get("/api/v1/incidents")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_incidents_with_pagination(self, client):
        """Pagination avec skip et limit."""
        with patch("app.api.v1.incidents.database") as mock_db:
            mock_db.list_incidents = AsyncMock(return_value=[])
            response = client.get("/api/v1/incidents?skip=0&limit=10")
        assert response.status_code == 200

    def test_list_incidents_invalid_limit(self, client):
        """Limit > 100 doit retourner 422."""
        response = client.get("/api/v1/incidents?limit=999")
        assert response.status_code == 422

    def test_list_incidents_negative_skip(self, client):
        """skip négatif doit retourner 422."""
        response = client.get("/api/v1/incidents?skip=-1")
        assert response.status_code == 422


class TestGetIncidentDetail:
    """Tests du GET /api/v1/incidents/{id}."""

    def test_get_existing_incident(self, client, sample_incident):
        """Récupérer un incident existant."""
        with patch("app.api.v1.incidents.database") as mock_db, \
             patch("app.api.v1.incidents.loki_client") as mock_loki, \
             patch("app.api.v1.incidents.prometheus_client") as mock_prom:
            mock_db.get_incident = AsyncMock(return_value=sample_incident)
            mock_loki.get_logs = AsyncMock(return_value=[])
            mock_prom.get_metrics = AsyncMock(return_value={})
            response = client.get("/api/v1/incidents/507f1f77bcf86cd799439011")
        assert response.status_code == 200

    def test_get_nonexistent_incident(self, client):
        """Incident inexistant doit retourner 404."""
        with patch("app.api.v1.incidents.database") as mock_db:
            mock_db.get_incident = AsyncMock(return_value=None)
            response = client.get("/api/v1/incidents/507f1f77bcf86cd799439011")
        assert response.status_code == 404
