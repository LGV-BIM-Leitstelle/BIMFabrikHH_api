"""Data endpoints reject an oversized umring before asking Hamburg."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.ogc_api.utils.user_messages import (
    AREA_LIMIT_MESSAGE,
    BOREHOLES_AREA_LIMIT_MESSAGE,
)
from src.api.web_app import create_app

pytestmark = [pytest.mark.unit]

# ~2.6 km x 2.2 km, over the 1 km² cap.
TWO_KM = {"min_x": 9.96, "min_y": 53.54, "max_x": 10.00, "max_y": 53.56}
# ~900 m x 900 m: under 1 km², over the 0.1 km² borehole cap.
ONE_KM = {"min_x": 9.9664, "min_y": 53.5594, "max_x": 9.9800, "max_y": 53.5675}

UMRING_ENDPOINTS = [
    "oaf-trees",
    "oaf-trees-hafen",
    "oaf-flurstuecke",
    "oaf-biotopes",
    "oaf-citymodell-tiles",
    "get-oaf-basic-tiles",
]


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture
def no_hamburg_requests():
    """Fail the test if an endpoint still sends a request to Hamburg."""
    asked = AssertionError("Hamburg was asked")
    with (
        patch("src.api.ogc_api.services.http_requests.HamburgOGCAPI.fetch_data", side_effect=asked),
        patch("src.api.ogc_api.services.http_requests.HamburgOGCAPI.get_tiles", side_effect=asked),
        patch("src.api.ogc_api.services.http_requests.WFSAPI.fetch_data", side_effect=asked),
    ):
        yield


@pytest.mark.parametrize("endpoint", UMRING_ENDPOINTS)
def test_oversized_umring_is_rejected_with_400(client, no_hamburg_requests, endpoint):
    response = client.get(f"/data/bimfabrikhh-datasets/{endpoint}", params=TWO_KM)
    assert response.status_code == 400
    assert response.json()["detail"] == AREA_LIMIT_MESSAGE


def test_borehole_umring_over_its_cap_is_rejected_with_400(client, no_hamburg_requests):
    response = client.get("/data/bimfabrikhh-datasets/wfs-boreholes", params=ONE_KM)
    assert response.status_code == 400
    assert response.json()["detail"] == BOREHOLES_AREA_LIMIT_MESSAGE


def test_umring_under_the_cap_is_passed_on(client):
    with patch(
        "src.api.data_api.oaf_endpoints.DataFetcher.fetch_tree_data",
        return_value={"type": "FeatureCollection", "features": []},
    ) as fetch:
        response = client.get("/data/bimfabrikhh-datasets/oaf-trees", params=ONE_KM)
    assert response.status_code == 200
    fetch.assert_called_once()
