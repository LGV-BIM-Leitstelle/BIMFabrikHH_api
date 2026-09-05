"""Umring area and tile-count limits."""

from BIMFabrikHH_core.data_models.params_bbox import BoundingBoxParams
from BIMFabrikHH_core.data_models.params_tree import RequestParams
import pytest

from src.api.ogc_api.utils.umring_limits import (
    MAX_BBOX_AREA_M2,
    MAX_TILES,
    bbox_area_m2,
    ensure_bbox_area,
    ensure_tile_count,
)
from src.api.ogc_api.utils.user_messages import AREA_LIMIT_MESSAGE, TILE_LIMIT_MESSAGE


def _params(min_x: float, min_y: float, max_x: float, max_y: float) -> RequestParams:
    return RequestParams(
        bbox=BoundingBoxParams(min_x=min_x, min_y=min_y, max_x=max_x, max_y=max_y)
    )


def test_compact_one_km_square_is_allowed():
    # ~900 m x 900 m — under 1 km² even when the box sits off-axis in UTM
    params = _params(9.9664, 53.5594, 9.9800, 53.5675)
    area = bbox_area_m2(params)
    assert area is not None
    assert area <= MAX_BBOX_AREA_M2
    ensure_bbox_area(params)


def test_two_km_square_is_rejected():
    params = _params(9.96, 53.54, 10.00, 53.56)
    area = bbox_area_m2(params)
    assert area is not None
    assert area > MAX_BBOX_AREA_M2
    with pytest.raises(ValueError, match=AREA_LIMIT_MESSAGE):
        ensure_bbox_area(params)


def test_area_just_over_one_km2_is_allowed(monkeypatch):
    monkeypatch.setattr(
        "src.api.ogc_api.utils.umring_limits.bbox_request_params_to_epsg25832",
        lambda _params: (0.0, 0.0, 1020.0, 1000.0),
    )
    ensure_bbox_area(_params(9.9664, 53.5594, 9.9800, 53.5675))


def test_area_over_rounding_slack_is_rejected(monkeypatch):
    monkeypatch.setattr(
        "src.api.ogc_api.utils.umring_limits.bbox_request_params_to_epsg25832",
        lambda _params: (0.0, 0.0, 1060.0, 1000.0),
    )
    with pytest.raises(ValueError, match=AREA_LIMIT_MESSAGE):
        ensure_bbox_area(_params(9.9664, 53.5594, 9.9800, 53.5675))


def test_tile_count_at_limit_is_allowed():
    ensure_tile_count(MAX_TILES)


def test_tile_count_over_limit_is_rejected():
    with pytest.raises(ValueError, match=TILE_LIMIT_MESSAGE):
        ensure_tile_count(MAX_TILES + 1)
