"""Base Pydantic models with timestamps."""
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class TimestampMixin(BaseModel):
    """Mixin that adds created_at and updated_at fields."""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BaseResponse(BaseModel):
    """Base response model."""
    success: bool = True
    message: str = ""
