"""
Redis-backed concurrency limiting for admission control.

This module encapsulates all Redis operations required to enforce a maximum
number of concurrently active Celery jobs per client identifier. It relies on
O(1) Redis Set operations (``SADD`` / ``SREM`` / ``SCARD``) rather than scanning
Celery metadata, and maintains a reverse lookup so that task lifecycle hooks can
release a slot knowing only the task ID.

Redis structure::

    active_jobs:<identifier>   Redis Set containing active task IDs
    job_owner:<task_id>        String -> owning client identifier

Copyright (C) 2025 Freie und Hansestadt Hamburg, Landesbetrieb Geoinformation und Vermessung
BIM-Leitstelle, Polichronis Muratidis <polichronis.muratidis@gv.hamburg.de>
"""

import logging
from typing import Optional

import redis

logger = logging.getLogger(__name__)

ACTIVE_JOBS_KEY_PREFIX = "active_jobs:"
JOB_OWNER_KEY_PREFIX = "job_owner:"


class ConcurrencyLimiter:
    """Enforce a per-identifier limit on concurrently active Celery jobs.

    All Redis interactions are contained within this class so callers only work
    with plain identifiers and task IDs.
    """

    def __init__(self, redis_client: redis.Redis, max_active_jobs: int) -> None:
        """Initialize the concurrency limiter.

        Args:
            redis_client: A synchronous Redis client (``decode_responses=True``
                is recommended so task IDs are returned as ``str``).
            max_active_jobs: Maximum number of concurrently active jobs allowed
                per client identifier.
        """
        self._redis = redis_client
        self._max_active_jobs = max_active_jobs

    @staticmethod
    def _active_jobs_key(identifier: str) -> str:
        return f"{ACTIVE_JOBS_KEY_PREFIX}{identifier}"

    @staticmethod
    def _job_owner_key(task_id: str) -> str:
        return f"{JOB_OWNER_KEY_PREFIX}{task_id}"

    @property
    def max_active_jobs(self) -> int:
        """Return the configured maximum number of concurrent jobs."""
        return self._max_active_jobs

    def active_job_count(self, identifier: str) -> int:
        """Return the number of currently active jobs for an identifier.

        Uses ``SCARD`` for an O(1) cardinality check.
        """
        return int(self._redis.scard(self._active_jobs_key(identifier)))

    def has_capacity(self, identifier: str) -> bool:
        """Return ``True`` if the identifier may start another job."""
        return self.active_job_count(identifier) < self._max_active_jobs

    def register_job(self, identifier: str, task_id: str) -> None:
        """Register a submitted task as active for the given identifier.

        Adds the task ID to the identifier's active-jobs set and stores the
        reverse lookup used during cleanup.
        """
        pipe = self._redis.pipeline()
        pipe.sadd(self._active_jobs_key(identifier), task_id)
        pipe.set(self._job_owner_key(task_id), identifier)
        pipe.execute()
        logger.debug("Registered job %s for identifier %s", task_id, identifier)

    def release_job(self, task_id: str) -> Optional[str]:
        """Release the concurrency slot held by a task.

        Looks up the owning identifier via the reverse lookup, removes the task
        ID from the owner's active-jobs set (``SREM``) and deletes the reverse
        lookup key. Safe to call multiple times; a missing task is a no-op.

        Args:
            task_id: The Celery task ID whose slot should be released.

        Returns:
            The owning identifier if it was found, otherwise ``None``.
        """
        owner = self._redis.get(self._job_owner_key(task_id))
        if owner is None:
            logger.debug("No owner found for task %s; nothing to release", task_id)
            return None

        # redis may return bytes if decode_responses is not set; normalize.
        if isinstance(owner, bytes):
            owner = owner.decode("utf-8")

        pipe = self._redis.pipeline()
        pipe.srem(self._active_jobs_key(owner), task_id)
        pipe.delete(self._job_owner_key(task_id))
        pipe.execute()
        logger.debug("Released job %s for identifier %s", task_id, owner)
        return owner
