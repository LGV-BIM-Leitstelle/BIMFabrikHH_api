"""
Unit tests for application-level admission control.

Covers the reusable client-identity abstraction, the Redis-backed concurrency
limiter, and the admission controller that ties them together. Redis is faked
with an in-memory double so the tests run without a live Redis instance.
"""

from unittest.mock import Mock, patch

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
        self.zsets = {}
        # key -> TTL in seconds, as passed via SET ... EX. Recorded rather than
        # enforced; expiry is simulated explicitly in tests via expire_key().
        self.expirations = {}

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

    # --- sorted set operations ---
    def zadd(self, key, mapping):
        z = self.zsets.setdefault(key, {})
        added = 0
        for member, score in mapping.items():
            if member not in z:
                added += 1
            z[member] = score
        return added

    def zcard(self, key):
        return len(self.zsets.get(key, {}))

    def zrem(self, key, *members):
        z = self.zsets.get(key, {})
        removed = 0
        for m in members:
            if m in z:
                del z[m]
                removed += 1
        return removed

    def zremrangebyscore(self, key, min_score, max_score):
        z = self.zsets.get(key, {})
        low = float("-inf") if min_score == "-inf" else float(min_score)
        high = float("inf") if max_score == "+inf" else float(max_score)
        stale = [m for m, score in z.items() if low <= score <= high]
        for m in stale:
            del z[m]
        return len(stale)

    def zscore(self, key, member):
        return self.zsets.get(key, {}).get(member)

    # --- string operations ---
    def set(self, key, value, ex=None):
        self.strings[key] = value
        if ex is not None:
            self.expirations[key] = ex
        return True

    def get(self, key):
        return self.strings.get(key)

    def delete(self, *keys):
        deleted = 0
        for key in keys:
            if key in self.strings:
                del self.strings[key]
                self.expirations.pop(key, None)
                deleted += 1
        return deleted

    # --- test helpers ---
    def expire_key(self, key):
        """Simulate Redis expiring a key whose TTL has elapsed."""
        self.strings.pop(key, None)
        self.expirations.pop(key, None)

    def age_member(self, key, member, seconds):
        """Backdate a sorted set member's score to simulate the passage of time."""
        self.zsets[key][member] -= seconds

    # --- pipeline ---
    def pipeline(self):
        return FakePipeline(self)


class FakePipeline:
    """Fake pipeline that records commands and applies them on execute()."""

    def __init__(self, client):
        self._client = client
        self._commands = []

    def sadd(self, key, *members):
        self._commands.append(("sadd", key, members, {}))
        return self

    def set(self, key, value, ex=None):
        self._commands.append(("set", key, (value,), {"ex": ex}))
        return self

    def srem(self, key, *members):
        self._commands.append(("srem", key, members, {}))
        return self

    def zadd(self, key, mapping):
        self._commands.append(("zadd", key, (mapping,), {}))
        return self

    def zcard(self, key):
        self._commands.append(("zcard", key, (), {}))
        return self

    def zrem(self, key, *members):
        self._commands.append(("zrem", key, members, {}))
        return self

    def zremrangebyscore(self, key, min_score, max_score):
        self._commands.append(("zremrangebyscore", key, (min_score, max_score), {}))
        return self

    def delete(self, *keys):
        self._commands.append(("delete", keys, (), {}))
        return self

    def execute(self):
        results = []
        for name, key, args, kwargs in self._commands:
            if name == "sadd":
                results.append(self._client.sadd(key, *args))
            elif name == "set":
                results.append(self._client.set(key, args[0], ex=kwargs["ex"]))
            elif name == "srem":
                results.append(self._client.srem(key, *args))
            elif name == "zadd":
                results.append(self._client.zadd(key, args[0]))
            elif name == "zcard":
                results.append(self._client.zcard(key))
            elif name == "zrem":
                results.append(self._client.zrem(key, *args))
            elif name == "zremrangebyscore":
                results.append(self._client.zremrangebyscore(key, *args))
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


class TestConcurrencySlotExpiry:
    """Tests for the TTL safety net that prevents permanently leaked slots.

    Slots are normally freed by the task lifecycle signals. When that never
    happens - an OOM-killed worker, a killed container, or a message removed
    from the broker before a worker saw it - the slot must still be reclaimed,
    otherwise the client stays blocked forever.
    """

    @pytest.fixture
    def redis_client(self):
        return FakeRedis()

    @pytest.fixture
    def limiter(self, redis_client):
        return ConcurrencyLimiter(
            redis_client=redis_client, max_active_jobs=2, slot_ttl_seconds=60
        )

    def test_fresh_slots_are_not_pruned(self, limiter):
        limiter.register_job("client-a", "task-1")
        limiter.register_job("client-a", "task-2")
        assert limiter.active_job_count("client-a") == 2

    def test_stale_slot_is_pruned_on_read(self, limiter, redis_client):
        limiter.register_job("client-a", "task-1")
        limiter.register_job("client-a", "task-2")
        assert limiter.has_capacity("client-a") is False

        # Simulate a job whose release signal never fired.
        redis_client.age_member("active_jobs_v2:client-a", "task-1", 120)

        assert limiter.active_job_count("client-a") == 1
        assert limiter.has_capacity("client-a") is True

    def test_leaked_slot_recovers_without_manual_intervention(
        self, limiter, redis_client
    ):
        """A client blocked by leaked slots un-blocks itself once they age out."""
        limiter.register_job("client-a", "task-1")
        limiter.register_job("client-a", "task-2")
        assert limiter.has_capacity("client-a") is False

        for task_id in ("task-1", "task-2"):
            redis_client.age_member("active_jobs_v2:client-a", task_id, 120)
            redis_client.expire_key(f"job_owner:{task_id}")

        assert limiter.active_job_count("client-a") == 0
        assert limiter.has_capacity("client-a") is True

    def test_register_sets_ttl_on_owner_key(self, limiter, redis_client):
        limiter.register_job("client-a", "task-1")
        assert redis_client.expirations["job_owner:task-1"] == 60

    def test_release_after_owner_expired_returns_none(self, limiter, redis_client):
        limiter.register_job("client-a", "task-1")
        redis_client.expire_key("job_owner:task-1")
        assert limiter.release_job("task-1") is None

    def test_pruning_is_per_identifier(self, limiter, redis_client):
        limiter.register_job("client-a", "task-1")
        limiter.register_job("client-b", "task-2")
        redis_client.age_member("active_jobs_v2:client-a", "task-1", 120)

        assert limiter.active_job_count("client-a") == 0
        assert limiter.active_job_count("client-b") == 1


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


class TestTaskFailureSignalReleasesSlot:
    """Tests for the ``task_failure`` signal handler that fixes the hard-timeout leak."""

    @patch("src.api.ogc_api.services.admission_controller.get_admission_controller")
    @patch("src.api.config.settings.admission_control_enabled", return_value=True)
    def test_on_task_failure_releases_admission_slot(
        self, mock_enabled, mock_get_controller
    ):
        from src.api.ogc_api.services.generate_bim_modells import _on_task_failure

        mock_controller = Mock()
        mock_get_controller.return_value = mock_controller

        _on_task_failure(task_id="task-timeout-1")

        mock_controller.release_job.assert_called_once_with("task-timeout-1")

    @patch("src.api.ogc_api.services.admission_controller.get_admission_controller")
    @patch("src.api.config.settings.admission_control_enabled", return_value=False)
    def test_on_task_failure_noop_when_admission_control_disabled(
        self, mock_enabled, mock_get_controller
    ):
        from src.api.ogc_api.services.generate_bim_modells import _on_task_failure

        _on_task_failure(task_id="task-timeout-2")

        mock_get_controller.assert_not_called()

    @patch("src.api.ogc_api.services.admission_controller.get_admission_controller")
    @patch("src.api.config.settings.admission_control_enabled", return_value=True)
    def test_on_task_failure_noop_without_task_id(
        self, mock_enabled, mock_get_controller
    ):
        from src.api.ogc_api.services.generate_bim_modells import _on_task_failure

        _on_task_failure(task_id=None)

        mock_get_controller.assert_not_called()
