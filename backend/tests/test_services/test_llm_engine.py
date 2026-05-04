"""Tests unitaires du LLMEngine."""
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


class TestLLMEngine:
    @pytest.mark.asyncio
    async def test_analyze_success(self):
        """analyze doit retourner un dict de diagnostic."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '{"cause_racine": "OOM", "solution": "Increase limits", "severite": "haute", "categorie": "resource_exhaustion"}'

        with patch("app.services.llm_engine._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            from app.services.llm_engine import analyze
            result = await analyze(
                alert_name="OOMKilled",
                message="Container killed",
                labels={"pod": "test-pod", "namespace": "test-ns"},
                cleaned_logs=["ERROR: OOM"],
                metrics={"memory_usage_bytes": 512000000},
            )

        assert "cause_racine" in result
        assert "solution" in result
        assert "severite" in result
        assert "categorie" in result

    @pytest.mark.asyncio
    async def test_analyze_json_parse_error(self):
        """En cas de JSON invalide, retourner un diagnostic d'erreur."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "This is not JSON"

        with patch("app.services.llm_engine._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            from app.services.llm_engine import analyze
            result = await analyze(
                alert_name="TestAlert",
                message="Test",
                labels={},
                cleaned_logs=[],
                metrics={},
            )

        assert result["categorie"] == "parse_error"

    @pytest.mark.asyncio
    async def test_analyze_api_error(self):
        """En cas d'erreur API, retourner un diagnostic d'erreur."""
        with patch("app.services.llm_engine._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(side_effect=Exception("API Error"))
            mock_get_client.return_value = mock_client

            from app.services.llm_engine import analyze
            result = await analyze(
                alert_name="TestAlert",
                message="Test",
                labels={},
                cleaned_logs=[],
                metrics={},
            )

        assert result["categorie"] == "api_error"

    @pytest.mark.asyncio
    async def test_chat_about_incident(self):
        """chat_about_incident doit retourner une réponse string."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Voici la réponse à votre question."

        with patch("app.services.llm_engine._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            from app.services.llm_engine import chat_about_incident
            result = await chat_about_incident(
                incident={"alert_name": "OOMKilled", "message": "OOM", "diagnostic": {}, "status": "ouvert"},
                question="Comment résoudre ?"
            )

        assert isinstance(result, str)
        assert len(result) > 0
