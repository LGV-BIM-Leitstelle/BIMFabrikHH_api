"""
Rate limiting for OGC process execution using FastAPI-Limiter and Redis.

This module wires FastAPI-Limiter to Redis with a custom identifier function so
that the rate limit is applied per client identifier (client IP from
``X-Forwarded-For``, falling back to ``request.client.host``) rather than
globally. The limiter is exposed as a single route dependency
(:data:`execution_rate_limit`) that is attached only to the process execution
endpoint.

Copyright (C) 2025 Freie und Hansestadt Hamburg, Landesbetrieb Geoinformation und Vermessung
BIM-Leitstelle, Polichronis Muratidis <polichronis.muratidis@gv.hamburg.de>
"""

import logging

import redis.asyncio as redis_asyncio
from fastapi import Request, Response
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter

from src.api.config.settings import api_settings

from .client_identity import get_client_identifier

logger = logging.getLogger(__name__)


async def rate_limit_identifier(request: Request) -> str:
    """FastAPI-Limiter identifier callback.

    Reuses the shared client-identity abstraction so rate limiting and
    concurrency limiting always key off the same identifier.
    """
    return get_client_identifier(request)


async def init_rate_limiter() -> None:
    """Initialize FastAPI-Limiter with a Redis connection.

    Must be called once during application startup before the rate limit
    dependency is used.
    """
    connection = redis_asyncio.from_url(
        api_settings.redis_url, encoding="utf-8", decode_responses=True
    )
    await FastAPILimiter.init(connection, identifier=rate_limit_identifier)
    logger.info(
        "Rate limiter initialized: %s requests / %s seconds per client identifier",
        api_settings.RATE_LIMIT_TIMES,
        api_settings.RATE_LIMIT_SECONDS,
    )


async def close_rate_limiter() -> None:
    """Release the FastAPI-Limiter Redis connection during shutdown."""
    if FastAPILimiter.redis is not None:
        await FastAPILimiter.close()
        logger.info("Rate limiter connection closed")


# The underlying FastAPI-Limiter dependency enforcing the configured budget.
_execution_rate_limiter = RateLimiter(
    times=api_settings.RATE_LIMIT_TIMES,
    seconds=api_settings.RATE_LIMIT_SECONDS,
)


async def execution_rate_limit(request: Request, response: Response) -> None:
    """Route dependency enforcing the per-identifier execution rate limit.

    When FastAPI-Limiter has not been initialized (for example in unit tests
    that construct the app without running its lifespan) the limiter is skipped
    rather than raising, keeping the endpoint usable in isolation.
    """
    if FastAPILimiter.redis is None:
        logger.warning(
            "FastAPILimiter not initialized; skipping rate limit for this request"
        )
        return
    await _execution_rate_limiter(request, response)
