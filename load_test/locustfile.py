"""
Locust load test for the BIMFabrikHH OGC API - Processes.

Scenario
--------
Each simulated user performs the full asynchronous OGC processing workflow,
picking one of the configured processes (``generate-tree-model``,
``generate-city-model``, ``generate-dgm-model``) with equal weight per task:

1. ``POST /ogc/processes/{processId}/execution`` with a randomized bounding
   box, which enqueues a Celery job and returns ``201`` with a ``jobId``.
2. Poll ``GET /ogc/jobs/{jobId}`` until the job status is ``successful`` or
   ``failed`` (or a client-side timeout is reached).

The bounding box is drawn per request from a distribution anchored on a fixed
central-Hamburg point (see ``_random_bbox``): a Gaussian-jittered center and
log-normal width/height. Set the module-level ``RANDOMIZE_BBOX`` flag to False
to send the fixed anchor box on every request instead.

Admission control
-----------------
Rate limiting (``RATE_LIMIT_TIMES`` requests / ``RATE_LIMIT_SECONDS``) and the
per-client concurrency limit (``MAX_CONCURRENT_JOBS``) are enforced *in the
application* (FastAPI-Limiter + AdmissionController), not by Traefik. Both key
off the client identifier, which is the left-most entry of the
``X-Forwarded-For`` header (see ``services/client_identity.py``). Traefik simply
forwards that header through.

To make every simulated user a distinct client (so a single source IP is not
throttled for the whole swarm), each user is assigned a unique, stable
``X-Forwarded-For`` IP. Because both the rate limit and the concurrency limit
answer with HTTP ``429``, a ``429`` is treated as an *expected* admission-control
response and tracked separately rather than counted as a failure.

Running
-------
Point ``--host`` at the Traefik entrypoint of the redis-backed stack (admission
control is only active with the ``--db redis`` backend). The WSL IP changes per
start; obtain it via ``hostname -I``::

    # Web UI
    locust -f load_test/locustfile.py --host http://<wsl-ip>:8081

    # Headless, 20 users, spawn 2/s, run for 5 minutes
    locust -f load_test/locustfile.py --host http://<wsl-ip>:8081 \
        --headless -u 20 -r 2 -t 5m

Copyright (C) 2025 Freie und Hansestadt Hamburg, Landesbetrieb Geoinformation und Vermessung
BIM-Leitstelle, Polichronis Muratidis <polichronis.muratidis@gv.hamburg.de>
"""

import itertools
import math
import random
import time

from locust import FastHttpUser, between, task

# --- Configuration -----------------------------------------------------------

# Default target: local Traefik entrypoint (override with --host on the CLI).
DEFAULT_HOST = "http://localhost:8081"

# OGC processes under test. Each task picks one of these with equal weight.
PROCESS_IDS = (
    "generate-tree-model",
    "generate-city-model",
    "generate-dgm-model",
)

# Bounding box randomization.
#
# When ``RANDOMIZE_BBOX`` is True, every request draws a fresh bounding box from
# an underlying distribution anchored on a fixed point in central Hamburg (the
# lower-left corner of the original box), which is treated as the "true" mean.
# When False, every request reuses the fixed anchor box (anchor as lower-left
# corner + the base extents), reproducing the original deterministic payload.
#
# * Center point: isotropic 2D Gaussian defined in METERS and converted to
#   degrees per axis. Longitude degrees are shorter than latitude degrees at
#   53.5 N, so an equal sigma in degrees would bias the spread N-S; defining
#   sigma in meters keeps the spread circular on the ground.
# * Width / height: log-normal (positive-only, multiplicative, right-skewed).
#   The MEDIAN is anchored to the original box dimension; sigma is in log-space.
#   Draws are clamped to a sane multiplicative range to trim extreme tails.

# Master switch: draw randomized boxes (True) or use the fixed anchor box (False).
RANDOMIZE_BBOX = True

# Fixed anchor = lower-left corner of the original box = mean of the center point.
CENTER_MEAN_LON = 9.992790
CENTER_MEAN_LAT = 53.550603

# Original box extents in degrees, used as the median of the size distributions.
BASE_WIDTH_DEG = 0.0033  # lon extent, ~218 m at this latitude
BASE_HEIGHT_DEG = 0.0014  # lat extent, ~156 m

# Center: standard deviation of the Gaussian jitter, in meters (isotropic).
CENTER_SIGMA_METERS = 1000.0

# Size: standard deviation of the log-normal in log-space (~+/-28% at 0.25).
SIZE_LOG_SIGMA = 0.5

# Size clamps as multiples of the base dimension (trim log-normal tails).
SIZE_MIN_FACTOR = 0.2
SIZE_MAX_FACTOR = 4

# WGS84 meters-per-degree approximations at the anchor latitude.
_METERS_PER_DEG_LAT = 111_320.0
_METERS_PER_DEG_LON = 111_320.0 * math.cos(math.radians(CENTER_MEAN_LAT))


def _random_bbox() -> dict:
    """Draw a randomized bounding box around the central Hamburg anchor.

    The center point is jittered with an isotropic Gaussian (defined in meters),
    and the width/height are drawn independently from log-normal distributions
    whose median equals the original box extent. The box is reconstructed from
    the sampled center and size, guaranteeing ``min < max``.
    """
    # Center: Gaussian jitter in meters, converted to degrees per axis.
    center_lon = (
        CENTER_MEAN_LON + random.gauss(0.0, CENTER_SIGMA_METERS) / _METERS_PER_DEG_LON
    )
    center_lat = (
        CENTER_MEAN_LAT + random.gauss(0.0, CENTER_SIGMA_METERS) / _METERS_PER_DEG_LAT
    )

    # Size: log-normal with median anchored to the base dimension.
    width = random.lognormvariate(math.log(BASE_WIDTH_DEG), SIZE_LOG_SIGMA)
    height = random.lognormvariate(math.log(BASE_HEIGHT_DEG), SIZE_LOG_SIGMA)

    # Clamp to a sane multiplicative range of the base dimension.
    width = min(
        max(width, BASE_WIDTH_DEG * SIZE_MIN_FACTOR), BASE_WIDTH_DEG * SIZE_MAX_FACTOR
    )
    height = min(
        max(height, BASE_HEIGHT_DEG * SIZE_MIN_FACTOR),
        BASE_HEIGHT_DEG * SIZE_MAX_FACTOR,
    )

    return {
        "min_x": center_lon - width / 2.0,
        "min_y": center_lat - height / 2.0,
        "max_x": center_lon + width / 2.0,
        "max_y": center_lat + height / 2.0,
    }


def _fixed_bbox() -> dict:
    """Return the deterministic anchor box (anchor as lower-left corner)."""
    return {
        "min_x": CENTER_MEAN_LON,
        "min_y": CENTER_MEAN_LAT,
        "max_x": CENTER_MEAN_LON + BASE_WIDTH_DEG,
        "max_y": CENTER_MEAN_LAT + BASE_HEIGHT_DEG,
    }


def _make_bbox() -> dict:
    """Return a randomized or fixed bounding box per ``RANDOMIZE_BBOX``."""
    return _random_bbox() if RANDOMIZE_BBOX else _fixed_bbox()


# Job polling behaviour.
POLL_INTERVAL_SECONDS = 5.0
POLL_TIMEOUT_SECONDS = 300.0

# Terminal OGC job states.
_TERMINAL_STATES = frozenset({"successful", "failed", "dismissed"})

# Locust request names (keep the stats table stable and readable). The execute
# and job-completion names are per-process so the stats table breaks results
# down by process; job-status polling is grouped under a single name.
_NAME_JOB_STATUS = "GET /ogc/jobs/[jobId]"


def _name_execute(process_id: str) -> str:
    return f"POST /ogc/processes/{process_id}/execution"


def _name_job_completion(process_id: str) -> str:
    return f"job completion (end-to-end) [{process_id}]"


# Thread-safe unique-IP generator. Mapped into the 100.64.0.0/10 CGNAT range so
# the spoofed X-Forwarded-For values never collide with real infrastructure IPs.
_ip_counter = itertools.count()


def _next_forwarded_ip() -> str:
    """Return a unique, stable ``X-Forwarded-For`` IP for a simulated user."""
    n = next(_ip_counter)
    # 100.64.0.0/10 has room for ~4M addresses; encode the counter across the
    # lower three octets so each user gets a distinct client identifier.
    octet_c = (n // 65536) % 64
    octet_a = (n // 256) % 256
    octet_b = n % 256
    return f"100.{64 + octet_c}.{octet_a}.{octet_b}"


def _build_inputs_payload() -> dict:
    """Build the OGC execution request body for the tree-model process."""
    return {
        "inputs": {
            "bbox": _make_bbox(),
            "containers": [
                {
                    "containerTitle": "Load Test Container",
                    "containerId": "load_test_container",
                    "components": {
                        "load_test_component": {
                            "title": "Load Test Component",
                            "value": "load test value",
                        }
                    },
                }
            ],
        }
    }


class OGCProcessUser(FastHttpUser):
    """Simulates a client submitting a process and polling until completion."""

    host = DEFAULT_HOST
    wait_time = between(1, 3)

    def on_start(self) -> None:
        """Assign a unique client identity and build reusable headers."""
        self.forwarded_ip = _next_forwarded_ip()
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            # In-app admission control keys off the left-most XFF entry; Traefik
            # forwards this header through unchanged.
            "X-Forwarded-For": self.forwarded_ip,
        }

    @task
    def execute_and_poll(self) -> None:
        """POST a process execution, then poll the job until it settles."""
        # Equal-weight choice across all configured processes.
        process_id = random.choice(PROCESS_IDS)
        job_id = self._submit_job(process_id)
        if job_id is not None:
            self._poll_job(process_id, job_id)

    def _submit_job(self, process_id: str) -> str | None:
        """Submit the process execution.

        Returns:
            The job id on ``201``. ``None`` if the request was rejected by
            admission control (``429``, expected) or otherwise did not yield a
            job to poll.
        """
        with self.client.request(
            "POST",
            f"/ogc/processes/{process_id}/execution",
            json=_build_inputs_payload(),
            headers=self.headers,
            name=_name_execute(process_id),
            catch_response=True,
        ) as resp:
            # 429 = admission control (rate limit or concurrency limit). This is
            # an expected outcome under load, not a server failure.
            if resp.status_code == 429:
                # resp.success()
                resp.failure("Request rejected by admission control (429)")
                return None

            if resp.status_code != 201:
                resp.failure(f"Unexpected status {resp.status_code} submitting job")
                return None

            try:
                job_id = resp.json().get("id")
            except Exception as exc:  # noqa: BLE001 - report as request failure
                resp.failure(f"Could not parse job id from response: {exc}")
                return None

            if not job_id:
                resp.failure("Response 201 but no job id present")
                return None

            resp.success()
            return job_id

    def _poll_job(self, process_id: str, job_id: str) -> None:
        """Poll job status until it is terminal or the timeout elapses."""
        start = time.monotonic()

        while True:
            elapsed = time.monotonic() - start
            if elapsed > POLL_TIMEOUT_SECONDS:
                self._report_completion(
                    process_id,
                    elapsed,
                    success=False,
                    error=f"Polling timed out after {POLL_TIMEOUT_SECONDS:.0f}s",
                )
                return

            status, message = self._get_job_status(job_id)

            if status in _TERMINAL_STATES:
                # "failed"/"dismissed" are legitimate terminal outcomes of the
                # workflow; the end-to-end metric records whether it succeeded.
                if status == "successful":
                    error = None
                else:
                    # Surface the backend-provided failure reason when present
                    # (e.g. hard bbox bounds exceeded), falling back to status.
                    error = f"Job {status}: {message}" if message else f"Job {status}"
                self._report_completion(
                    process_id,
                    time.monotonic() - start,
                    success=(status == "successful"),
                    error=error,
                )
                return

            time.sleep(POLL_INTERVAL_SECONDS)

    def _get_job_status(self, job_id: str) -> tuple[str | None, str | None]:
        """Fetch a single job status.

        Returns:
            A ``(status, message)`` tuple. ``message`` is the backend-provided
            failure reason (present on ``failed`` jobs) or ``None``. On a
            transport/parse error both elements are ``None``.
        """
        with self.client.request(
            "GET",
            f"/ogc/jobs/{job_id}",
            headers={"Accept": "application/json"},
            name=_NAME_JOB_STATUS,
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"Unexpected status {resp.status_code} polling job")
                return None, None
            try:
                body = resp.json()
                status = body.get("status")
                message = body.get("message")
            except Exception as exc:  # noqa: BLE001 - report as request failure
                resp.failure(f"Could not parse job status: {exc}")
                return None, None

            resp.success()
            return status, message

    def _report_completion(
        self, process_id: str, duration_seconds: float, success: bool, error: str | None
    ) -> None:
        """Emit a synthetic request event for end-to-end job completion time."""
        self.environment.events.request.fire(
            request_type="JOB",
            name=_name_job_completion(process_id),
            response_time=duration_seconds * 1000.0,
            response_length=0,
            exception=None if success else Exception(error or "job did not succeed"),
            context={},
        )
