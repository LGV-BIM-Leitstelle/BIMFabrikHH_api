"""
Client identity resolution for admission control.

This module provides a reusable abstraction for deriving a stable client
identifier from an incoming request. Today the identifier is the client IP
address (extracted from the ``X-Forwarded-For`` header, falling back to the
direct peer address). The abstraction is intentionally isolated so it can later
be swapped for authenticated user IDs without touching the router, the rate
limiter, or the concurrency controller.

Copyright (C) 2025 Freie und Hansestadt Hamburg, Landesbetrieb Geoinformation und Vermessung
BIM-Leitstelle, Polichronis Muratidis <polichronis.muratidis@gv.hamburg.de>
"""

from typing import Callable

from fastapi import Request

# Type alias describing the client identifier abstraction. Any callable that
# maps a request to a stable string identifier satisfies this contract, which
# keeps the rate limiter and concurrency controller decoupled from *how* a
# client is identified.
ClientIdentifier = Callable[[Request], str]

_UNKNOWN_CLIENT = "unknown"


def get_client_identifier(request: Request) -> str:
    """Derive a stable client identifier from the request.

    The identifier is the client IP address taken from the first entry of the
    ``X-Forwarded-For`` header (set by upstream proxies / load balancers),
    falling back to ``request.client.host`` when the header is absent.

    Args:
        request: The incoming FastAPI/Starlette request.

    Returns:
        A non-empty string identifying the client.
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For may contain a comma-separated list of proxies;
        # the left-most entry is the originating client.
        client_ip = forwarded_for.split(",")[0].strip()
        if client_ip:
            return client_ip

    if request.client and request.client.host:
        return request.client.host

    return _UNKNOWN_CLIENT
