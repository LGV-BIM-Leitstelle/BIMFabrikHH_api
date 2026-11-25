"""Internal errors are mapped to the UI message constants."""

import pytest
import requests

from src.api.ogc_api.utils.user_messages import (
    AREA_LIMIT_MESSAGE,
    BASEPOINT_OUTSIDE_CRS_MESSAGE,
    BIOTOPES_IFC_FAILED_MESSAGE,
    BOREHOLES_AREA_LIMIT_MESSAGE,
    DATA_SERVICE_UNAVAILABLE_MESSAGE,
    INVALID_INPUT_MESSAGE,
    CORE_BOREHOLES_MISSING_MESSAGE,
    NO_BIOTOPES_DATA_MESSAGE,
    NO_BIOTOPES_MESSAGE,
    NO_BOREHOLES_MESSAGE,
    NO_BUILDINGS_MESSAGE,
    NO_TREES_MESSAGE,
    TERRAIN_IFC_FAILED_MESSAGE,
    TILE_LIMIT_MESSAGE,
    UNEXPECTED_ERROR_MESSAGE,
    to_user_error,
)


def _http_error(status: int) -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status
    return requests.HTTPError(f"{status} Server Error", response=response)


@pytest.mark.parametrize(
    "incoming, expected",
    [
        (ValueError(TILE_LIMIT_MESSAGE), TILE_LIMIT_MESSAGE),
        (ValueError(AREA_LIMIT_MESSAGE), AREA_LIMIT_MESSAGE),
        (ValueError(BOREHOLES_AREA_LIMIT_MESSAGE), BOREHOLES_AREA_LIMIT_MESSAGE),
        (ValueError(NO_BUILDINGS_MESSAGE), NO_BUILDINGS_MESSAGE),
        (ValueError(NO_BIOTOPES_DATA_MESSAGE), NO_BIOTOPES_DATA_MESSAGE),
        (ValueError(NO_BIOTOPES_MESSAGE), NO_BIOTOPES_MESSAGE),
        (ValueError(BIOTOPES_IFC_FAILED_MESSAGE), BIOTOPES_IFC_FAILED_MESSAGE),
        (RuntimeError("no buildings parsed from CityGML"), NO_BUILDINGS_MESSAGE),
        (RuntimeError("no trees to write"), NO_TREES_MESSAGE),
        (RuntimeError("terrain mesh has no faces"), TERRAIN_IFC_FAILED_MESSAGE),
        (RuntimeError("no borehole records"), NO_BOREHOLES_MESSAGE),
        (
            ImportError("bimfabrikhh-core borehole app is required"),
            CORE_BOREHOLES_MISSING_MESSAGE,
        ),
        (
            ValueError(
                "1 validation error for RequestParams\n  Value error, "
                "(5933559.0, 565012.0) lies outside the area of use of EPSG:25832"
            ),
            BASEPOINT_OUTSIDE_CRS_MESSAGE,
        ),
        (
            ValueError(
                "1 validation error for RequestParams\n  Value error, "
                "The bbox lies outside the area of use of EPSG:10285"
            ),
            INVALID_INPUT_MESSAGE,
        ),
        (ValueError("1 validation error for RequestParams"), INVALID_INPUT_MESSAGE),
        (Exception("connection reset"), UNEXPECTED_ERROR_MESSAGE),
        (requests.ConnectionError("connection refused"), DATA_SERVICE_UNAVAILABLE_MESSAGE),
        (requests.Timeout("read timed out"), DATA_SERVICE_UNAVAILABLE_MESSAGE),
        (_http_error(503), DATA_SERVICE_UNAVAILABLE_MESSAGE),
        (_http_error(404), UNEXPECTED_ERROR_MESSAGE),
    ],
)
def test_to_user_error_maps_to_ui_message(incoming, expected):
    mapped = to_user_error(incoming)
    assert isinstance(mapped, ValueError)
    assert str(mapped) == expected
