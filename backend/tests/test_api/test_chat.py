"""Tests de l'endpoint POST /api/v1/chat."""
from unittest.mock import AsyncMock, patch
import pytest


class TestChatEndpoint:
    """Tests du POST /api/v1/chat."""

    def test_chat_valid_request(self, client, sample_incident):
        """Chat valide doit retourner 200."""
        with patch("app.api.v1.chat.database") as mock_db, \
             patch("app.api.v1.chat.llm_engine") as mock_llm:
            mock_db.get_incident = AsyncMock(return_value=sample_incident)
            mock_llm.chat_about_incident = AsyncMock(return_value="Voici la réponse.")
            response = client.post("/api/v1/chat", json={
                "incident_id": "507f1f77bcf86cd799439011",
                "question": "Comment résoudre ce problème ?"
            })
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "incident_id" in data

    def test_chat_incident_not_found(self, client):
        """Incident inexistant doit retourner 404."""
        with patch("app.api.v1.chat.database") as mock_db:
            mock_db.get_incident = AsyncMock(return_value=None)
            response = client.post("/api/v1/chat", json={
                "incident_id": "507f1f77bcf86cd799439011",
                "question": "Quelle est la cause ?"
            })
        assert response.status_code == 404

    def test_chat_missing_fields(self, client):
        """Champs manquants doit retourner 422."""
        response = client.post("/api/v1/chat", json={"question": "Test"})
        assert response.status_code == 422
