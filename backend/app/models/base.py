"""Base Pydantic models with timestamps."""
from datetime import datetime
from pydantic import BaseModel, Field


class TimestampMixin(BaseModel):
    """Mixin that adds created_at and updated_at fields."""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class BaseResponse(BaseModel):
    """Base response model."""
    success: bool = True
    message: str = ""
