"""Dependency injection helpers for LangGraph investigation pipeline."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.graph_pipeline import InvestigationPipeline


@lru_cache
def get_investigation_pipeline() -> InvestigationPipeline:
    """Provide a singleton investigation pipeline instance."""
    return InvestigationPipeline()


InvestigationPipelineDependency = Annotated[InvestigationPipeline, Depends(get_investigation_pipeline)]
