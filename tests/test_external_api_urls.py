"""
Integration tests for external Hamburg OGC API URLs configured in .env.

These tests call the live Hamburg APIs via DataFetcher and the Data API
endpoints. They verify that TREES_API_URL, TREES_HAFEN_API_URL, and
DGM_TILES_API_URL are reachable and return valid responses.

Requires network access and a configured .env file.

Run only these tests:
    pytest tests/test_external_api_urls.py -m external_api -v

Skip them in the default fast suite:
    pytest tests/ -m "not external_api and not requires_worker"
"""

from __future__ import annotations

import re
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from src.api.config import api_settings
from src.api.ogc_api.services.http_requests import DataFetcher, HamburgOGCAPI
from src.api.web_app import create_app

pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
    pytest.mark.external_api,
]

# Small bbox in central Hamburg (known street-tree coverage from production logs).
HAMBURG_TREE_BBOX: Dict[str, float] = {
    "min_x": 9.9756,
    "min_y": 53.5522,
    "max_x": 9.9789,
    "max_y": 53.5536,
}

# Harbor area bbox (HafenCity / Landungsbrücken vicinity).
HAMBURG_HAFEN_BBOX: Dict[str, float] = {
    "min_x": 9.9650,
    "min_y": 53.5380,
    "max_x": 9.9950,
    "max_y": 53.5480,
}

DGM_TILE_PATTERN = re.compile(r"^dgm1_32_\d+_\d+_1_hh_2022\.tif$")


def _assert_feature_collection(data: Dict[str, Any]) -> None:
    assert isinstance(data, dict)
    assert data.get("type") == "FeatureCollection"
    assert "features" in data
    assert isinstance(data["features"], list)


def _assert_point_feature(feature: Dict[str, Any]) -> None:
    assert "geometry" in feature
    geometry = feature["geometry"]
    assert geometry.get("type") in {"Point", "MultiPoint"}
    assert "coordinates" in geometry
    assert "properties" in feature


@pytest.fixture(scope="module")
def live_client() -> TestClient:
    return TestClient(create_app())


class TestEnvApiUrlConfiguration:
    """Verify the three external API URLs are loaded from .env."""

    def test_trees_api_url_configured(self) -> None:
        url = str(api_settings.TREES_API_URL)
        assert url.startswith("https://")
        assert "strassenbaumkataster" in url
        assert url.endswith("/items")

    def test_trees_hafen_api_url_configured(self) -> None:
        url = str(api_settings.TREES_HAFEN_API_URL)
        assert url.startswith("https://")
        assert "strassenbaumkataster_hafen" in url
        assert url.endswith("/items")

    def test_dgm_tiles_api_url_configured(self) -> None:
        url = str(api_settings.DGM_TILES_API_URL)
        assert url.startswith("https://")
        assert "lgv_kachel_dk5_1km_utm" in url
        assert url.endswith("/items")


class TestTreesApiUrl:
    """Live tests for TREES_API_URL."""

    def test_fetch_tree_data_returns_feature_collection(self) -> None:
        data = DataFetcher.fetch_tree_data(HAMBURG_TREE_BBOX)
        _assert_feature_collection(data)
        assert len(data["features"]) > 0
        _assert_point_feature(data["features"][0])

    def test_trees_url_matches_env_setting(self) -> None:
        params = {
            "f": "json",
            "bbox": (
                f"{HAMBURG_TREE_BBOX['min_x']},{HAMBURG_TREE_BBOX['min_y']},"
                f"{HAMBURG_TREE_BBOX['max_x']},{HAMBURG_TREE_BBOX['max_y']}"
            ),
            "crs": HamburgOGCAPI.DEFAULT_CRS,
            "limit": 10,
            "skipGeometry": "false",
        }
        data = HamburgOGCAPI.fetch_data(str(api_settings.TREES_API_URL), params)
        _assert_feature_collection(data)


class TestTreesHafenApiUrl:
    """Live tests for TREES_HAFEN_API_URL."""

    def test_fetch_tree_data_hafen_returns_feature_collection(self) -> None:
        data = DataFetcher.fetch_tree_data_hafen(HAMBURG_HAFEN_BBOX)
        _assert_feature_collection(data)

    def test_hafen_url_matches_env_setting(self) -> None:
        params = {
            "f": "json",
            "bbox": (
                f"{HAMBURG_HAFEN_BBOX['min_x']},{HAMBURG_HAFEN_BBOX['min_y']},"
                f"{HAMBURG_HAFEN_BBOX['max_x']},{HAMBURG_HAFEN_BBOX['max_y']}"
            ),
            "crs": HamburgOGCAPI.DEFAULT_CRS,
            "limit": 10,
            "skipGeometry": "false",
        }
        data = HamburgOGCAPI.fetch_data(str(api_settings.TREES_HAFEN_API_URL), params)
        _assert_feature_collection(data)


class TestDgmTilesApiUrl:
    """Live tests for DGM_TILES_API_URL."""

    def test_dgm_tiles_url_returns_feature_collection(self) -> None:
        params = {
            "f": "json",
            "bbox": (
                f"{HAMBURG_TREE_BBOX['min_x']},{HAMBURG_TREE_BBOX['min_y']},"
                f"{HAMBURG_TREE_BBOX['max_x']},{HAMBURG_TREE_BBOX['max_y']}"
            ),
            "skipGeometry": "false",
        }
        data = HamburgOGCAPI.fetch_data(str(api_settings.DGM_TILES_API_URL), params)
        _assert_feature_collection(data)
        assert len(data["features"]) > 0
        assert "kachelbezeichnung_dk5" in data["features"][0].get("properties", {})

    def test_fetch_dgm_tiles_returns_tif_filenames(self) -> None:
        tiles = DataFetcher.fetch_dgm_tiles(HAMBURG_TREE_BBOX)
        assert isinstance(tiles, list)
        assert len(tiles) > 0
        assert all(DGM_TILE_PATTERN.match(tile) for tile in tiles)


class TestDataApiOafEndpoints:
    """Live tests for Data API routes that proxy the same env URLs."""

    def test_oaf_trees_endpoint(self, live_client: TestClient) -> None:
        response = live_client.get(
            "/data/bimfabrikhh-datasets/oaf-trees",
            params=HAMBURG_TREE_BBOX,
        )
        assert response.status_code == 200
        data = response.json()
        _assert_feature_collection(data)
        assert len(data["features"]) > 0

    def test_oaf_trees_hafen_endpoint(self, live_client: TestClient) -> None:
        response = live_client.get(
            "/data/bimfabrikhh-datasets/oaf-trees-hafen",
            params=HAMBURG_HAFEN_BBOX,
        )
        assert response.status_code == 200
        _assert_feature_collection(response.json())

    def test_oaf_dgm_tiles_endpoint(self, live_client: TestClient) -> None:
        response = live_client.get(
            "/data/bimfabrikhh-datasets/get-oaf-basic-tiles",
            params=HAMBURG_TREE_BBOX,
        )
        assert response.status_code == 200
        tiles = response.json()
        assert isinstance(tiles, list)
        assert len(tiles) > 0
        assert all(DGM_TILE_PATTERN.match(tile) for tile in tiles)
