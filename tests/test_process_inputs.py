"""Tests for the client inputs of a process (``ProcessInputs``)."""

import pytest
from BIMFabrikHH_core.data_models.params_tree import RequestParams
from pydantic import ValidationError

from src.api.ogc_api.models.process_inputs import ProcessInputs

BBOX = {"min_x": 9.9756, "min_y": 53.5522, "max_x": 9.9789, "max_y": 53.5536}


def test_fields_are_core_request_params_without_api_set_codes():
    """New core fields must be added here too; the API sets the two source codes."""
    assert set(ProcessInputs.model_fields) == set(RequestParams.model_fields) - {
        "source_epsg",
        "vertical_epsg",
    }


@pytest.mark.parametrize("field", ["source_epsg", "vertical_epsg"])
def test_api_set_codes_are_rejected(field):
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ProcessInputs(bbox=BBOX, **{field: 25832})


def test_output_epsg_must_be_projected():
    with pytest.raises(ValidationError, match="not a 2D projected"):
        ProcessInputs(bbox=BBOX, output_epsg=4326)


def test_to_request_params_sets_the_fetch_crs():
    request_params = ProcessInputs(bbox=BBOX, output_epsg=10285).to_request_params(
        25832, 7837
    )
    assert isinstance(request_params, RequestParams)
    assert (
        request_params.source_epsg,
        request_params.output_epsg,
        request_params.vertical_epsg,
    ) == (25832, 10285, 7837)
    assert request_params.bbox_as_wgs84_tuple == tuple(BBOX.values())
