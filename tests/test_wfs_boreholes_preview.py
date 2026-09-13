"""Preview count for Bohrungen filtern uses the Header WFS, not the full model."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from lxml import etree

from src.api.data_api.oaf_endpoints import BMLH_NS, _borehole_header_preview
from src.api.web_app import create_app


@pytest.fixture
def client():
    return TestClient(create_app())


def _header_collection(*projects: str) -> etree._Element:
    members = []
    for index, project in enumerate(projects, start=1):
        members.append(
            f"""
            <wfs:member>
              <bmlh:BoreholeHeader>
                <bmlh:id>BDHH_{index}</bmlh:id>
                <bmlh:project>{project}</bmlh:project>
              </bmlh:BoreholeHeader>
            </wfs:member>
            """
        )
    xml = f"""
    <wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0"
        xmlns:bmlh="{BMLH_NS}">
      {"".join(members)}
    </wfs:FeatureCollection>
    """
    return etree.fromstring(xml.encode())


def test_header_preview_counts_and_unique_projects():
    root = _header_collection("Projekt A", "Projekt B", "Projekt A")
    count, projekte = _borehole_header_preview(root)
    assert count == 3
    assert projekte == ["Projekt A", "Projekt B"]


def test_header_preview_empty_xml():
    assert _borehole_header_preview(None) == (0, [])


def test_wfs_boreholes_endpoint_uses_header_fetch(client):
    root = _header_collection("Deichbau")
    with patch(
        "src.api.data_api.oaf_endpoints.DataFetcher.fetch_borehole_header_data",
        return_value=root,
    ) as mock_fetch:
        response = client.get(
            "/data/bimfabrikhh-datasets/wfs-boreholes",
            params={
                "min_x": 9.9861,
                "min_y": 53.4867,
                "max_x": 9.9872,
                "max_y": 53.4872,
            },
        )
    assert response.status_code == 200
    data = response.json()
    mock_fetch.assert_called_once()
    assert data["count"] == 1
    assert data["projekte"] == ["Deichbau"]
    assert data["message"] == "1 Bohrung wurde gefunden"


def test_wfs_boreholes_endpoint_plural_message(client):
    root = _header_collection("A", "B")
    with patch(
        "src.api.data_api.oaf_endpoints.DataFetcher.fetch_borehole_header_data",
        return_value=root,
    ):
        response = client.get(
            "/data/bimfabrikhh-datasets/wfs-boreholes",
            params={
                "min_x": 9.9861,
                "min_y": 53.4867,
                "max_x": 9.9872,
                "max_y": 53.4872,
            },
        )
    assert response.json()["message"] == "2 Bohrungen wurden gefunden"
