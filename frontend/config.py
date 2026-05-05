"""Application configuration for Streamlit UI."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Environment-driven configuration."""

    backend_url: str = os.getenv("BACKEND_URL", "http://localhost:8000/api/v1")
    request_timeout: float = float(os.getenv("REQUEST_TIMEOUT", "10"))
    cache_ttl_seconds: int = int(os.getenv("CACHE_TTL_SECONDS", "30"))
    max_log_lines: int = int(os.getenv("MAX_LOG_LINES", "100"))
    max_metrics_points: int = int(os.getenv("MAX_METRICS_POINTS", "100"))


settings = Settings()
