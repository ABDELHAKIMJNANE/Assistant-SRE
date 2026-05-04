"""Custom exceptions for centralized error handling."""


class AIOpsException(Exception):
    """Base exception for AIOps backend."""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class DatabaseException(AIOpsException):
    def __init__(self, message: str = "Database operation failed"):
        super().__init__(message, status_code=503)


class LLMException(AIOpsException):
    def __init__(self, message: str = "LLM service unavailable"):
        super().__init__(message, status_code=503)


class NotFoundException(AIOpsException):
    def __init__(self, resource: str = "Resource"):
        super().__init__(f"{resource} not found", status_code=404)


class ValidationException(AIOpsException):
    def __init__(self, message: str = "Validation error"):
        super().__init__(message, status_code=422)


class RateLimitException(AIOpsException):
    def __init__(self):
        super().__init__("Rate limit exceeded", status_code=429)
