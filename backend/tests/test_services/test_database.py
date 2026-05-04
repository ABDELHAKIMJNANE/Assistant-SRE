"""Tests unitaires du service database."""
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


class TestDatabaseService:
    """Tests du CosmosDBClient."""

    @pytest.mark.asyncio
    async def test_insert_incident(self):
        """insert_incident doit retourner un ID string."""
        mock_result = MagicMock()
        mock_result.inserted_id = "507f1f77bcf86cd799439011"
        mock_collection = MagicMock()
        mock_collection.insert_one = AsyncMock(return_value=mock_result)
        mock_db_instance = MagicMock()
        mock_db_instance.__getitem__ = MagicMock(return_value=mock_collection)

        with patch("app.services.database.get_db", return_value=mock_db_instance):
            from app.services.database import insert_incident
            result = await insert_incident({"alert_name": "TestAlert", "status": "ouvert"})
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_find_past_incident_not_found(self):
        """find_past_incident retourne None si aucun résultat."""
        mock_collection = MagicMock()
        mock_collection.find_one = AsyncMock(return_value=None)
        mock_db_instance = MagicMock()
        mock_db_instance.__getitem__ = MagicMock(return_value=mock_collection)

        with patch("app.services.database.get_db", return_value=mock_db_instance):
            from app.services.database import find_past_incident
            result = await find_past_incident("NonExistentAlert")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_incidents_empty(self):
        """list_incidents retourne une liste vide si pas d'incidents."""
        mock_cursor = MagicMock()
        mock_cursor.sort = MagicMock(return_value=mock_cursor)
        mock_cursor.skip = MagicMock(return_value=mock_cursor)
        mock_cursor.limit = MagicMock(return_value=mock_cursor)

        async def async_iter():
            return
            yield  # make it a generator

        mock_cursor.__aiter__ = lambda self: async_iter()
        mock_collection = MagicMock()
        mock_collection.find = MagicMock(return_value=mock_cursor)
        mock_db_instance = MagicMock()
        mock_db_instance.__getitem__ = MagicMock(return_value=mock_collection)

        with patch("app.services.database.get_db", return_value=mock_db_instance):
            from app.services.database import list_incidents
            result = await list_incidents(skip=0, limit=20)
        assert result == []
