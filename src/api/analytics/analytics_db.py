"""Dedicated PostGIS store for bounding-box request analytics.

This module is deliberately **independent** from ``src/database/db_utils.py``
(the Celery SQLite result backend). It owns a separate SQLAlchemy engine that
talks to a dedicated PostGIS database belonging to the *monitoring* stack
(service ``analytics-postgres``), not to the application's own persistence.

Design constraints:

* **Best-effort.** Recording analytics must never affect the API request path.
  Engine creation, schema bootstrap and inserts are all wrapped; failures are
  logged and swallowed, never raised to the caller.
* **DSGVO / GDPR.** Only the requested geographic extent is stored (center
  point, bounding-box polygon, area, model type, optional DGM flag). No client
  IP, no job/task id — nothing that links a bounding box to an identifiable
  person. The extent alone, over public open geodata, is not personal data.
* **Retention.** Rows older than ``ANALYTICS_RETENTION_DAYS`` are deleted
  opportunistically (at most once per hour per process) to match the 15-day
  window used by Prometheus and Loki.
"""

from __future__ import annotations

import logging
import threading
import time

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

from src.api.config.settings import api_settings

logger = logging.getLogger(__name__)


def _log_db_failure(message: str, exc: Exception) -> None:
    """Log an analytics DB failure."""
    if isinstance(exc, OperationalError):
        logger.warning("%s: analytics DB unreachable (%s)", message, exc.orig or exc)
    else:
        logger.exception(message)


# Lazily-initialized engine shared across the process.
_engine: Engine | None = None
_engine_lock = threading.Lock()

# Schema is bootstrapped once per process.
_schema_ready = False
_schema_lock = threading.Lock()

# Retention runs at most once per hour per process.
_PURGE_INTERVAL_SECONDS = 3600
_last_purge_monotonic = 0.0
_purge_lock = threading.Lock()


def _get_engine() -> Engine | None:
    """Return the shared SQLAlchemy engine, creating it on first use.

    Returns ``None`` (and logs) if the engine cannot be created, so callers can
    silently skip recording when the analytics DB is unavailable.
    """
    global _engine
    if _engine is not None:
        return _engine
    with _engine_lock:
        if _engine is not None:
            return _engine
        try:
            from sqlalchemy import create_engine

            _engine = create_engine(
                api_settings.analytics_db_url,
                pool_pre_ping=True,
                pool_size=2,
                max_overflow=2,
                pool_recycle=1800,
                # Keep the request path snappy even if the DB is slow/unreachable.
                connect_args={
                    "connect_timeout": 5,
                    "options": "-c statement_timeout=5000",
                },
            )
            logger.info(
                "Analytics DB engine initialized (host=%s port=%s db=%s)",
                api_settings.ANALYTICS_DB_HOST,
                api_settings.ANALYTICS_DB_PORT,
                api_settings.ANALYTICS_DB_NAME,
            )
        except Exception as exc:
            _log_db_failure("Failed to initialize analytics DB engine", exc)
            _engine = None
    return _engine


def _ensure_schema(engine: Engine) -> None:
    """Create the PostGIS extension, table and indexes if missing (idempotent)."""
    global _schema_ready
    if _schema_ready:
        return
    with _schema_lock:
        if _schema_ready:
            return
        srid = int(api_settings.ANALYTICS_BBOX_SRID)
        statements = [
            "CREATE EXTENSION IF NOT EXISTS postgis",
            (
                "CREATE TABLE IF NOT EXISTS analytics_bbox ("
                " id BIGSERIAL PRIMARY KEY,"
                " created_at TIMESTAMPTZ NOT NULL DEFAULT now(),"
                " model_type TEXT NOT NULL,"
                " use_dgm_elevation BOOLEAN,"
                " area_m2 DOUBLE PRECISION NOT NULL,"
                f" center geometry(Point, {srid}) NOT NULL,"
                f" bbox geometry(Polygon, {srid}) NOT NULL"
                ")"
            ),
            "CREATE INDEX IF NOT EXISTS idx_analytics_bbox_created_at ON analytics_bbox (created_at)",
            "CREATE INDEX IF NOT EXISTS idx_analytics_bbox_center ON analytics_bbox USING GIST (center)",
        ]
        with engine.begin() as conn:
            for stmt in statements:
                conn.execute(text(stmt))
        _schema_ready = True
        logger.info("Analytics DB schema ready (table analytics_bbox, srid=%s)", srid)


_INSERT_SQL = text("""
    WITH env AS (
        SELECT ST_MakeEnvelope(:min_x, :min_y, :max_x, :max_y, :srid) AS geom
    )
    INSERT INTO analytics_bbox (model_type, use_dgm_elevation, area_m2, center, bbox)
    SELECT :model_type, :use_dgm, :area_m2, ST_Centroid(env.geom), env.geom
    FROM env
    """)

_PURGE_SQL = text(
    "DELETE FROM analytics_bbox WHERE created_at < now() - make_interval(days => :days)"
)


def _maybe_purge(conn) -> None:
    """Delete expired rows, throttled to at most once per hour per process."""
    global _last_purge_monotonic
    now = time.monotonic()
    with _purge_lock:
        if now - _last_purge_monotonic < _PURGE_INTERVAL_SECONDS:
            return
        _last_purge_monotonic = now
    conn.execute(_PURGE_SQL, {"days": int(api_settings.ANALYTICS_RETENTION_DAYS)})


def insert_bbox_event(
    model_type: str,
    bbox: tuple[float, float, float, float],
    area_m2: float,
    use_dgm_elevation: bool | None,
) -> None:
    """Persist one bounding-box analytics event (best-effort).

    Args:
        model_type: OGC process id (e.g. ``generate-tree-model``).
        bbox: ``(min_x, min_y, max_x, max_y)`` in ``ANALYTICS_BBOX_SRID``.
        area_m2: Requested area in square meters.
        use_dgm_elevation: Tree-model DGM flag if present, else ``None``.
    """
    engine = _get_engine()
    if engine is None:
        return
    try:
        _ensure_schema(engine)
        min_x, min_y, max_x, max_y = bbox
        with engine.begin() as conn:
            conn.execute(
                _INSERT_SQL,
                {
                    "min_x": min_x,
                    "min_y": min_y,
                    "max_x": max_x,
                    "max_y": max_y,
                    "srid": int(api_settings.ANALYTICS_BBOX_SRID),
                    "model_type": model_type,
                    "use_dgm": use_dgm_elevation,
                    "area_m2": area_m2,
                },
            )
            _maybe_purge(conn)
    except Exception as exc:
        _log_db_failure("Failed to record bbox analytics event", exc)
