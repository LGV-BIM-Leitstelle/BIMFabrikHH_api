"""Bounding-box request analytics (DSGVO-safe, identity-decoupled).

Public entry point :func:`record_bbox_request` fans one accepted processing
request out to two sinks:

* Prometheus (``bbox_requests_total`` + ``bbox_area_square_meters``) for size
  and volume KPIs, exposed on the existing ``/metrics`` endpoint.
* A dedicated PostGIS store (``analytics_bbox``) for the geospatial "locations
  of interest" heatmap in Grafana.

Only the geographic extent is recorded — never the client IP or job id — so the
data cannot be tied to an identifiable person. All work is best-effort and
gated behind the ``ENABLE_ANALYTICS`` setting.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping

from src.api.config.settings import api_settings

from .analytics_db import insert_bbox_event
from .metrics import observe_bbox_metrics

logger = logging.getLogger(__name__)

_WGS84_SRID = 4326


def _area_m2(min_x: float, min_y: float, max_x: float, max_y: float) -> float:
    """Approximate bounding-box area in square meters.

    For geographic input (SRID 4326, lon/lat degrees) an equirectangular
    approximation at the box's mean latitude is used — accurate to well within
    1% for city-scale boxes, which is ample for a metrics histogram. For a
    projected (metric) SRID the extent is already in meters, so the planar
    product is exact.
    """
    if int(api_settings.ANALYTICS_BBOX_SRID) == _WGS84_SRID:
        mean_lat = math.radians((min_y + max_y) / 2.0)
        width_m = abs(max_x - min_x) * 111_320.0 * math.cos(mean_lat)
        height_m = abs(max_y - min_y) * 110_540.0
        return width_m * height_m
    return abs(max_x - min_x) * abs(max_y - min_y)


def record_bbox_request(
    model_type: str,
    bbox: Mapping[str, float],
    use_dgm_elevation: bool | None = None,
) -> None:
    """Record one accepted processing request (best-effort, never raises).

    Intended to be scheduled as a FastAPI background task so neither the metric
    update nor the database write ever adds latency to the client response.

    Args:
        model_type: OGC process id (e.g. ``generate-tree-model``).
        bbox: Mapping with ``min_x``, ``min_y``, ``max_x``, ``max_y`` in
            ``ANALYTICS_BBOX_SRID`` (WGS84 lon/lat by default).
        use_dgm_elevation: Tree-model DGM flag if present, else ``None``.
    """
    if not api_settings.ENABLE_ANALYTICS:
        return

    try:
        min_x = float(bbox["min_x"])
        min_y = float(bbox["min_y"])
        max_x = float(bbox["max_x"])
        max_y = float(bbox["max_y"])
    except (KeyError, TypeError, ValueError):
        logger.warning("Skipping bbox analytics: malformed bbox %r", bbox)
        return

    area_m2 = _area_m2(min_x, min_y, max_x, max_y)

    try:
        observe_bbox_metrics(model_type, area_m2)
    except Exception:
        logger.exception("Failed to observe bbox Prometheus metrics")

    insert_bbox_event(
        model_type, (min_x, min_y, max_x, max_y), area_m2, use_dgm_elevation
    )


__all__ = ["record_bbox_request"]
