"""Health check endpoints for K8s probes."""
import logging
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.services.database import get_db
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health/live", tags=["Health"], summary="Liveness probe")
async def liveness() -> dict[str, str]:
    """K8s liveness probe — confirms the app is running."""
    return {"status": "alive", "service": "aiops-sre-backend"}


@router.get("/health/ready", tags=["Health"], summary="Readiness probe")
async def readiness() -> dict[str, Any]:
    """
    K8s readiness probe — confirms the app is ready to serve traffic.
    Checks MongoDB connectivity.
    """
    checks: dict[str, str] = {}

    # Check MongoDB
    try:
        db = get_db()
        await db.command("ping")
        checks["mongodb"] = "ok"
    except Exception as e:
        logger.error(f"❌ MongoDB health check failed: {e}")
        checks["mongodb"] = f"error: {str(e)}"

    all_ok = all(v == "ok" for v in checks.values())
    status_code = 200 if all_ok else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if all_ok else "not_ready",
            "checks": checks,
        },
    )


@router.get("/health/startup", tags=["Health"], summary="Startup probe")
async def startup() -> dict[str, str]:
    """K8s startup probe — confirms initial startup is complete."""
    return {"status": "started", "version": settings.app_version if hasattr(settings, 'app_version') else "1.0.0"}
