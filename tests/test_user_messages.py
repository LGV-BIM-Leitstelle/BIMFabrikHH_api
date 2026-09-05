"""Internal errors are mapped to the UI message constants."""

import pytest

from src.api.ogc_api.utils.user_messages import (
    INVALID_INPUT_MESSAGE,
    NO_BUILDINGS_MESSAGE,
    NO_TREES_MESSAGE,
    TERRAIN_IFC_FAILED_MESSAGE,
    TILE_LIMIT_MESSAGE,
    UNEXPECTED_ERROR_MESSAGE,
    to_user_error,
)


@pytest.mark.parametrize(
    "incoming, expected",
    [
        (ValueError(TILE_LIMIT_MESSAGE), TILE_LIMIT_MESSAGE),
        (ValueError(NO_BUILDINGS_MESSAGE), NO_BUILDINGS_MESSAGE),
        (RuntimeError("no buildings parsed from CityGML"), NO_BUILDINGS_MESSAGE),
        (RuntimeError("no trees to write"), NO_TREES_MESSAGE),
        (RuntimeError("terrain mesh has no faces"), TERRAIN_IFC_FAILED_MESSAGE),
        (ValueError("1 validation error for RequestParams"), INVALID_INPUT_MESSAGE),
        (Exception("connection reset"), UNEXPECTED_ERROR_MESSAGE),
    ],
)
def test_to_user_error_maps_to_ui_message(incoming, expected):
    mapped = to_user_error(incoming)
    assert isinstance(mapped, ValueError)
    assert str(mapped) == expected
