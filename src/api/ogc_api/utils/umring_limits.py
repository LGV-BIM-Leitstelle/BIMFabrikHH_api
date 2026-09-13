"""Umring size limits enforced before model generation.

Numbers come from ``umring_limits.json`` next to ``.env`` at the API repo
root (not from the venv). Edit that file and restart the API to change caps.

DK5 / CityGML / DGM cells are 1 km × 1 km. A compact 1 km² window typically
touches at most four tiles (2 × 2 on a grid corner); six tiles leaves room
for a slightly elongated 1 km² box. The tile cap still rejects a thin strip
that stays under 1 km² but crosses many cells.

The hard caps are 1.05 km² and 0.105 km² so a UI that rounds up to
1 km² or 0.1 km² is not rejected.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from BIMFabrikHH_core.core.georeferencing import bbox_request_params_to_epsg25832
from BIMFabrikHH_core.data_models.params_tree import RequestParams

from src.api.config.settings import PROJECT_ROOT

from .user_messages import (
    AREA_LIMIT_MESSAGE,
    BOREHOLES_AREA_LIMIT_MESSAGE,
    TILE_LIMIT_MESSAGE,
)

UMRING_LIMITS_FILE = PROJECT_ROOT / "umring_limits.json"

_DEFAULTS: Dict[str, Any] = {
    "max_area_km2": 1.05,
    "borehole_max_area_km2": 0.105,
    "max_tiles": 6,
}


def _load_umring_limits() -> Dict[str, Any]:
    config = dict(_DEFAULTS)
    if UMRING_LIMITS_FILE.is_file():
        with UMRING_LIMITS_FILE.open(encoding="utf-8") as handle:
            loaded = json.load(handle)
        if isinstance(loaded, dict):
            config.update(loaded)
    return config


_LIMITS = _load_umring_limits()
DEFAULT_MAX_AREA_KM2 = float(_LIMITS["max_area_km2"])
BOREHOLE_MAX_AREA_KM2 = float(_LIMITS["borehole_max_area_km2"])
MAX_BBOX_AREA_M2 = round(DEFAULT_MAX_AREA_KM2 * 1_000_000)
MAX_BOREHOLE_BBOX_AREA_M2 = round(BOREHOLE_MAX_AREA_KM2 * 1_000_000)
MAX_TILES = int(_LIMITS["max_tiles"])


def bbox_area_m2(request_params: RequestParams) -> Optional[float]:
    """Planar area of the request bbox in EPSG:25832, or ``None`` if unset."""
    utm = bbox_request_params_to_epsg25832(request_params)
    if utm is None:
        return None
    min_x, min_y, max_x, max_y = utm
    return abs(max_x - min_x) * abs(max_y - min_y)


def ensure_bbox_area(
    request_params: RequestParams,
    *,
    max_area_m2: float = MAX_BBOX_AREA_M2,
    message: str = AREA_LIMIT_MESSAGE,
) -> None:
    """Raise when the umring is larger than ``max_area_m2``."""
    area = bbox_area_m2(request_params)
    if area is not None and area > max_area_m2:
        raise ValueError(message)


def ensure_borehole_bbox_area(request_params: RequestParams) -> None:
    """Raise when the borehole umring is larger than the configured cap."""
    ensure_bbox_area(
        request_params,
        max_area_m2=MAX_BOREHOLE_BBOX_AREA_M2,
        message=BOREHOLES_AREA_LIMIT_MESSAGE,
    )


def ensure_tile_count(tile_count: int) -> None:
    """Raise when more than :data:`MAX_TILES` cells are touched."""
    if tile_count > MAX_TILES:
        raise ValueError(TILE_LIMIT_MESSAGE)
