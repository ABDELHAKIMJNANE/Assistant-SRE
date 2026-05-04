"""Point d'entrée FastAPI — Lifespan et configuration de l'application."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.services.database import connect_db, close_db
from app.config import settings
from app.core.logging import setup_logging
from app.core.exceptions import AIOpsException, RateLimitException
from app.models.error import ErrorResponse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestion du cycle de vie : connexion DB au démarrage, fermeture à l'arrêt."""
    setup_logging(settings.log_level)
    logger.info("🚀 Démarrage du backend AIOps...", extra={"environment": settings.environment})
    await connect_db()
    logger.info("✅ Connexion MongoDB établie")
    yield
    await close_db()
    logger.info("🛑 Backend AIOps arrêté")


app = FastAPI(
    title="AIOps SRE Backend",
    description="Backend intelligent pour l'assistant SRE — Analyse d'alertes, diagnostic IA, Auto-Learning",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes API v1 ──
app.include_router(api_router, prefix="/api/v1")


# ── Centralized Error Handlers ──
@app.exception_handler(AIOpsException)
async def aiops_exception_handler(request: Request, exc: AIOpsException) -> JSONResponse:
    """Handle all custom AIOps exceptions."""
    logger.error(f"AIOps error: {exc.message}", extra={"path": str(request.url)})
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.message,
            status_code=exc.status_code,
        ).model_dump(),
    )


@app.exception_handler(RateLimitException)
async def rate_limit_exception_handler(request: Request, exc: RateLimitException) -> JSONResponse:
    """Handle rate limit exceptions."""
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"error": exc.message, "status_code": 429},
        headers={"Retry-After": str(settings.rate_limit_period)},
    )


@app.get("/healthz", tags=["Health"])
async def health_check():
    """Health check utilisé par K8s liveness probe."""
    return {"status": "ok"}
