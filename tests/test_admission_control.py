"""
Unit tests for application-level admission control.

Covers the reusable client-identity abstraction, the Redis-backed concurrency
limiter, and the admission controller that ties them together. Redis is faked
with an in-memory double so the tests run without a live Redis instance.
"""

from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from src.api.ogc_api.services.admission_controller import AdmissionController
from src.api.ogc_api.services.client_identity import get_client_identifier
from src.api.ogc_api.services.concurrency_limit import ConcurrencyLimiter


class FakeRedis:
    """Minimal in-memory stand-in for the Redis operations we rely on."""

    def __init__(self):
        self.sets = {}
        self.strings = {}

    # --- set operations ---
    def scard(self, key):
        return len(self.sets.get(key, set()))

    def sadd(self, key, *members):
        s = self.sets.setdefault(key, set())
        before = len(s)
        s.update(members)
        return len(s) - before

    def srem(self, key, *members):
        s = self.sets.get(key, set())
        removed = 0
        for m in members:
            if m in s:
                s.remove(m)
                removed += 1
        return removed

    # --- string operations ---
    def set(self, key, value):
        self.strings[key] = value
        return True

    def get(self, key):
        return self.strings.get(key)

    def delete(self, *keys):
        deleted = 0
        for key in keys:
            if key in self.strings:
                del self.strings[key]
                deleted += 1
        return deleted

    # --- pipeline ---
    def pipeline(self):
        return FakePipeline(self)


class FakePipeline:
    """Fake pipeline that records commands and applies them on execute()."""

    def __init__(self, client):
        self._client = client
        self._commands = []

    def sadd(self, key, *members):
        self._commands.append(("sadd", key, members))
        return self

    def set(self, key, value):
        self._commands.append(("set", key, (value,)))
        return self

    def srem(self, key, *members):
        self._commands.append(("srem", key, members))
        return self

    def delete(self, *keys):
        self._commands.append(("delete", keys, ()))
        return self

    def execute(self):
        results = []
        for name, key, args in self._commands:
            if name == "sadd":
                results.append(self._client.sadd(key, *args))
            elif name == "set":
                results.append(self._client.set(key, args[0]))
            elif name == "srem":
                results.append(self._client.srem(key, *args))
            elif name == "delete":
                results.append(self._client.delete(*key))
        self._commands.clear()
        return results


def make_request(headers=None, client_host="203.0.113.9"):
    """Build a minimal fake request exposing headers and client host."""
    request = Mock()
    request.headers = headers or {}
    if client_host is None:
        request.client = None
    else:
        request.client = Mock()
        request.client.host = client_host
    return request


class TestClientIdentity:
    """Tests for the reusable client identifier abstraction."""

    def test_uses_x_forwarded_for_first_entry(self):
        request = make_request(
            headers={"X-Forwarded-For": "198.51.100.7, 10.0.0.1"},
            client_host="10.0.0.1",
        )
        assert get_client_identifier(request) == "198.51.100.7"

    def test_falls_back_to_client_host(self):
        request = make_request(headers={}, client_host="203.0.113.9")
        assert get_client_identifier(request) == "203.0.113.9"

    def test_unknown_when_no_client(self):
        request = make_request(headers={}, client_host=None)
        assert get_client_identifier(request) == "unknown"


class TestConcurrencyLimiter:
    """Tests for the Redis-backed concurrency limiter."""

    @pytest.fixture
    def limiter(self):
        return ConcurrencyLimiter(redis_client=FakeRedis(), max_active_jobs=2)

    def test_capacity_available_when_empty(self, limiter):
        assert limiter.active_job_count("client-a") == 0
        assert limiter.has_capacity("client-a") is True

    def test_register_increments_count(self, limiter):
        limiter.register_job("client-a", "task-1")
        assert limiter.active_job_count("client-a") == 1
        assert limiter.has_capacity("client-a") is True

    def test_capacity_exhausted_at_limit(self, limiter):
        limiter.register_job("client-a", "task-1")
        limiter.register_job("client-a", "task-2")
        assert limiter.active_job_count("client-a") == 2
        assert limiter.has_capacity("client-a") is False

    def test_release_frees_slot(self, limiter):
        limiter.register_job("client-a", "task-1")
        limiter.register_job("client-a", "task-2")
        owner = limiter.release_job("task-1")
        assert owner == "client-a"
        assert limiter.active_job_count("client-a") == 1
        assert limiter.has_capacity("client-a") is True

    def test_release_unknown_task_is_noop(self, limiter):
        assert limiter.release_job("does-not-exist") is None

    def test_limits_are_per_identifier(self, limiter):
        limiter.register_job("client-a", "task-1")
        limiter.register_job("client-a", "task-2")
        assert limiter.has_capacity("client-a") is False
        # A different client is unaffected.
        assert limiter.has_capacity("client-b") is True


class TestAdmissionController:
    """Tests for the admission controller decision logic."""

    @pytest.fixture
    def controller(self):
        limiter = ConcurrencyLimiter(redis_client=FakeRedis(), max_active_jobs=2)
        return AdmissionController(concurrency_limiter=limiter)

    def test_ensure_capacity_passes_below_limit(self, controller):
        # Should not raise.
        controller.ensure_capacity("client-a")

    def test_ensure_capacity_rejects_at_limit(self, controller):
        controller.register_job("client-a", "task-1")
        controller.register_job("client-a", "task-2")
        with pytest.raises(HTTPException) as exc_info:
            controller.ensure_capacity("client-a")
        assert exc_info.value.status_code == 429

    def test_release_after_limit_allows_new_job(self, controller):
        controller.register_job("client-a", "task-1")
        controller.register_job("client-a", "task-2")
        controller.release_job("task-1")
        # Now there is capacity again.
        controller.ensure_capacity("client-a")
