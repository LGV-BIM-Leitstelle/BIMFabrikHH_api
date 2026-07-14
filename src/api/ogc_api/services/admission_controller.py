"""
Application-level admission control for OGC process execution.

The :class:`AdmissionController` is the single entry point the router uses to
decide whether a new process execution may be accepted. It encapsulates the
Redis-backed concurrency limiter so the router never touches Redis directly.

Rate limiting (requests per minute) is handled separately via FastAPI-Limiter
(see :mod:`rate_limit`) because it is enforced as a route dependency; this
controller focuses on the concurrent-job admission decision and on tracking the
lifecycle of accepted jobs.

Copyright (C) 2025 Freie und Hansestadt Hamburg, Landesbetrieb Geoinformation und Vermessung
BIM-Leitstelle, Polichronis Muratidis <polichronis.muratidis@gv.hamburg.de>
"""

import logging
from typing import Optional

import redis
from fastapi import HTTPException

from src.api.config.settings import api_settings

from .concurrency_limit import ConcurrencyLimiter

logger = logging.getLogger(__name__)


class AdmissionController:
    """Decide whether new jobs may be admitted and track their lifecycle.

    Concurrency operations are delegated to a :class:`ConcurrencyLimiter`, which
    keeps all Redis details out of both this class's callers and the router.
    """

    def __init__(self, concurrency_limiter: ConcurrencyLimiter) -> None:
        self._concurrency = concurrency_limiter

    def ensure_capacity(self, identifier: str) -> None:
        """Ensure the identifier may start another job.

        Args:
            identifier: The client identifier requesting a new job.

        Raises:
            HTTPException: ``429 Too Many Requests`` if the identifier already
                has the maximum number of concurrently active jobs.
        """
        if not self._concurrency.has_capacity(identifier):
            active = self._concurrency.active_job_count(identifier)
            logger.info(
                "Rejecting job for %s: %s active jobs (limit %s)",
                identifier,
                active,
                self._concurrency.max_active_jobs,
            )
            raise HTTPException(
                status_code=429,
                detail=(
                    "Maximum number of concurrent jobs "
                    f"({self._concurrency.max_active_jobs}) reached. "
                    "Please wait for a running job to finish before submitting a new one."
                ),
            )

    def register_job(self, identifier: str, task_id: str) -> None:
        """Register an accepted, submitted task as active."""
        self._concurrency.register_job(identifier, task_id)

    def release_job(self, task_id: str) -> Optional[str]:
        """Release the concurrency slot held by a completed/failed task."""
        return self._concurrency.release_job(task_id)


_admission_controller: Optional[AdmissionController] = None


def _build_admission_controller() -> AdmissionController:
    redis_client = redis.Redis.from_url(api_settings.redis_url, decode_responses=True)
    concurrency_limiter = ConcurrencyLimiter(
        redis_client=redis_client,
        max_active_jobs=api_settings.MAX_CONCURRENT_JOBS,
    )
    return AdmissionController(concurrency_limiter=concurrency_limiter)


def get_admission_controller() -> AdmissionController:
    """Return the process-wide :class:`AdmissionController` singleton.

    The controller (and its underlying Redis client) is created lazily on first
    use so that importing this module does not require a live Redis connection.
    """
    global _admission_controller
    if _admission_controller is None:
        _admission_controller = _build_admission_controller()
    return _admission_controller
