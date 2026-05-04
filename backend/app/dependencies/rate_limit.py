"""Rate limiting dependency."""
import time
import logging
from collections import defaultdict
from typing import Annotated

from fastapi import Depends, Request

from app.config import settings
from app.core.exceptions import RateLimitException

logger = logging.getLogger(__name__)

# In-memory store: {client_ip: [timestamps]}
_request_counts: dict[str, list[float]] = defaultdict(list)


async def rate_limit_check(request: Request) -> None:
    """
    Simple sliding-window rate limiter.
    Raises RateLimitException if client exceeds the configured limit.
    """
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    window_start = now - settings.rate_limit_period

    # Clean old requests
    _request_counts[client_ip] = [
        ts for ts in _request_counts[client_ip] if ts > window_start
    ]

    if len(_request_counts[client_ip]) >= settings.rate_limit_requests:
        logger.warning(f"⚠️ Rate limit exceeded for {client_ip}")
        raise RateLimitException()

    _request_counts[client_ip].append(now)


RateLimitDependency = Annotated[None, Depends(rate_limit_check)]
