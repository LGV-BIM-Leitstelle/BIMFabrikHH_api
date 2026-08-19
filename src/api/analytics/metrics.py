"""Prometheus metrics for bounding-box request analytics.

These metrics are registered on the default ``prometheus_client`` registry, the
same one exposed by the FastAPI instrumentator at ``GET /metrics``. Importing
this module is enough to register them.

Label discipline (matches the monitoring stack conventions): the only label is
``model_type`` (three low-cardinality values). Coordinates are never used as
labels — spatial data lives in the dedicated PostGIS store instead.
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram

# Count of processing requests accepted, partitioned by model type.
BBOX_REQUESTS = Counter(
    "bbox_requests_total",
    "Processing requests accepted at the OGC execution endpoint, by model type.",
    ["model_type"],
)

# Distribution of the requested bounding-box area (square meters), by model type.
# Buckets span ~1000 m2 (tiny box) to ~1e8 m2 (10 km x 10 km) to cover the
# realistic range of requests without excessive cardinality.
BBOX_AREA_SQUARE_METERS = Histogram(
    "bbox_area_square_meters",
    "Requested bounding-box area in square meters, by model type.",
    ["model_type"],
    buckets=(
        1_000.0,
        5_000.0,
        10_000.0,
        50_000.0,
        100_000.0,
        500_000.0,
        1_000_000.0,
        5_000_000.0,
        10_000_000.0,
        50_000_000.0,
        100_000_000.0,
    ),
)


def observe_bbox_metrics(model_type: str, area_m2: float) -> None:
    """Record one accepted request into the Prometheus metrics.

    Args:
        model_type: The OGC process id (e.g. ``generate-tree-model``).
        area_m2: Requested bounding-box area in square meters.
    """
    BBOX_REQUESTS.labels(model_type=model_type).inc()
    BBOX_AREA_SQUARE_METERS.labels(model_type=model_type).observe(area_m2)
