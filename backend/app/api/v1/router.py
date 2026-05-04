"""Agrégation de toutes les routes API v1."""

from fastapi import APIRouter

from app.api.v1.webhook import router as webhook_router
from app.api.v1.incidents import router as incidents_router
from app.api.v1.resolve import router as resolve_router
from app.api.v1.chat import router as chat_router
from app.api.v1.health import router as health_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(webhook_router)
api_router.include_router(incidents_router)
api_router.include_router(resolve_router)
api_router.include_router(chat_router)
