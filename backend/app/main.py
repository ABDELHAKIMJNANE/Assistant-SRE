"""Point d'entrée FastAPI — Lifespan et configuration de l'application."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.services.database import connect_db, close_db
from app.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestion du cycle de vie : connexion DB au démarrage, fermeture à l'arrêt."""
    logging.basicConfig(level=getattr(logging, settings.log_level))
    logger.info("🚀 Démarrage du backend AIOps...")
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

# ── CORS — Permettre les requêtes du frontend Streamlit ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes API v1 ──
app.include_router(api_router, prefix="/api/v1")


@app.get("/healthz", tags=["Health"])
async def health_check():
    """Health check utilisé par K8s liveness probe."""
    return {"status": "ok"}
