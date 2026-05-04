"""Tests unitaires du LokiClient."""
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import httpx


class TestLokiClient:
    @pytest.mark.asyncio
    async def test_get_logs_success(self):
        """get_logs doit retourner une liste de lignes."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "result": [
                    {
                        "values": [
                            ["1234567890", "ERROR: OOM killed"],
                            ["1234567891", "WARNING: High memory"],
                        ]
                    }
                ]
            }
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

            from app.services.loki_client import get_logs
            result = await get_logs(pod="test-pod", namespace="test-ns")

        assert isinstance(result, list)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_logs_http_error(self):
        """En cas d'erreur HTTP, retourner une liste vide."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.HTTPError("Connection refused"))
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

            from app.services.loki_client import get_logs
            result = await get_logs(pod="test-pod", namespace="test-ns")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_logs_empty_result(self):
        """Loki sans résultats doit retourner une liste vide."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": {"result": []}}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

            from app.services.loki_client import get_logs
            result = await get_logs(pod="test-pod", namespace="test-ns")

        assert result == []
