"""Async API client for the FastAPI backend."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Generic, Optional, TypeVar

import httpx

from config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class ApiResult(Generic[T]):
    data: Optional[T]
    error: Optional[str] = None


class BackendAPI:
    """HTTP client for backend endpoints."""

    def __init__(self, base_url: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def _request(self, method: str, path: str, **kwargs: Any) -> ApiResult[Any]:
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                return ApiResult(response.json())
        except httpx.HTTPError as exc:
            message = f"Backend request failed: {exc}"
            logger.warning(message)
            return ApiResult(None, message)
        except Exception as exc:
            message = f"Unexpected error: {exc}"
            logger.error(message)
            return ApiResult(None, message)

    def _request_sync(self, method: str, path: str, **kwargs: Any) -> ApiResult[Any]:
        url = f"{self.base_url}{path}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.request(method, url, **kwargs)
                response.raise_for_status()
                return ApiResult(response.json())
        except httpx.HTTPError as exc:
            message = f"Backend request failed: {exc}"
            logger.warning(message)
            return ApiResult(None, message)
        except Exception as exc:
            message = f"Unexpected error: {exc}"
            logger.error(message)
            return ApiResult(None, message)

    async def fetch_incidents(self, skip: int = 0, limit: int = 50) -> ApiResult[list[dict[str, Any]]]:
        return await self._request("GET", "/incidents", params={"skip": skip, "limit": limit})

    async def fetch_incident_detail(self, incident_id: str) -> ApiResult[dict[str, Any]]:
        return await self._request("GET", f"/incidents/{incident_id}")

    async def resolve_incident(self, incident_id: str, solution: str) -> ApiResult[dict[str, Any]]:
        payload = {"validated_solution": solution}
        return await self._request("PUT", f"/incidents/{incident_id}/resolve", json=payload)

    async def chat_incident(self, incident_id: str, question: str) -> ApiResult[dict[str, Any]]:
        payload = {"incident_id": incident_id, "question": question}
        return await self._request("POST", "/chat", json=payload)

    def fetch_incidents_sync(self, skip: int = 0, limit: int = 50) -> ApiResult[list[dict[str, Any]]]:
        return self._request_sync("GET", "/incidents", params={"skip": skip, "limit": limit})

    def fetch_incident_detail_sync(self, incident_id: str) -> ApiResult[dict[str, Any]]:
        return self._request_sync("GET", f"/incidents/{incident_id}")

    def resolve_incident_sync(self, incident_id: str, solution: str) -> ApiResult[dict[str, Any]]:
        payload = {"validated_solution": solution}
        return self._request_sync("PUT", f"/incidents/{incident_id}/resolve", json=payload)

    def chat_incident_sync(self, incident_id: str, question: str) -> ApiResult[dict[str, Any]]:
        payload = {"incident_id": incident_id, "question": question}
        return self._request_sync("POST", "/chat", json=payload)


def run_async(coro: Any, sync_fallback) -> Any:
    """Run async coroutine in a sync Streamlit context with a safe fallback."""

    try:
        return asyncio.run(coro)
    except RuntimeError as exc:
        try:
            coro.close()
        except Exception as close_exc:
            logger.debug("Failed to close coroutine cleanly: %s", close_exc)
        logger.warning("Async loop already running, using sync fallback: %s", exc)
        return sync_fallback()


api_client = BackendAPI(settings.backend_url, settings.request_timeout)


def get_incidents(skip: int = 0, limit: int = 50) -> ApiResult[list[dict[str, Any]]]:
    return run_async(
        api_client.fetch_incidents(skip=skip, limit=limit),
        lambda: api_client.fetch_incidents_sync(skip=skip, limit=limit),
    )


def get_incident_detail(incident_id: str) -> ApiResult[dict[str, Any]]:
    return run_async(
        api_client.fetch_incident_detail(incident_id),
        lambda: api_client.fetch_incident_detail_sync(incident_id),
    )


def resolve_incident(incident_id: str, solution: str) -> ApiResult[dict[str, Any]]:
    return run_async(
        api_client.resolve_incident(incident_id, solution),
        lambda: api_client.resolve_incident_sync(incident_id, solution),
    )


def chat_incident(incident_id: str, question: str) -> ApiResult[dict[str, Any]]:
    return run_async(
        api_client.chat_incident(incident_id, question),
        lambda: api_client.chat_incident_sync(incident_id, question),
    )
