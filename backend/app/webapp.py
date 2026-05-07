"""Webapp helpers for health/readiness metadata."""

from app.dependencies.investigation import get_investigation_pipeline


def get_webapp_health() -> dict[str, str]:
    """Return basic webapp health details including LangGraph readiness."""
    pipeline = get_investigation_pipeline()
    graph_status = "ready" if pipeline is not None else "not_ready"
    return {"status": "ok", "langgraph": graph_status}
