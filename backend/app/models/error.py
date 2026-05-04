"""Error response models."""
from typing import Any, Optional
from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """Single error detail."""
    field: Optional[str] = None
    message: str
    code: Optional[str] = None


class ErrorResponse(BaseModel):
    """Standard error response."""
    success: bool = False
    error: str
    details: Optional[list[ErrorDetail]] = None
    status_code: int


class HTTPErrorResponse(BaseModel):
    """HTTP error for OpenAPI documentation."""
    detail: str
