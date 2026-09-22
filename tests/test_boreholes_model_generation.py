"""
Tests for borehole (Baugrundaufschluss) model generation.

Tasks run in Celery eager mode (see the ``celery_eager_mode`` fixture in
conftest.py), so ``.delay()``/``.get()`` execute in-process without a running
worker or broker. Heavy core dependencies are mocked.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.api.ogc_api.services.generate_bim_modells import (
    execute_generate_boreholes_model,
)
from src.api.ogc_api.utils.user_messages import (
    BOREHOLES_AREA_LIMIT_MESSAGE,
    BOREHOLES_IFC_FAILED_MESSAGE,
    NO_BOREHOLE_DATA_MESSAGE,
    NO_BOREHOLES_MESSAGE,
    UNEXPECTED_ERROR_MESSAGE,
)

pytestmark = [pytest.mark.integration, pytest.mark.celery, pytest.mark.borehole]


@pytest.fixture(autouse=True)
def _enable_eager(celery_eager_mode):
    """Run all tasks in this module eagerly (no worker/broker required)."""
    yield


def _sample_records():
    return [
        SimpleNamespace(borehole_id="BDHH_1", aufschlussbezeichnung="B1", projekt="P1"),
    ]


class TestBoreholesModelGeneration:
    """Tests for borehole model generation."""

    def test_successful_boreholes_model_generation(
        self, valid_boreholes_request_params
    ):
        records = _sample_records()
        with patch(
            "src.api.ogc_api.services.generate_bim_modells.DataFetcher.fetch_borehole_data"
        ) as mock_fetch, patch(
            "src.api.ogc_api.services.generate_bim_modells.BoreholeMLProcessor"
        ) as mock_processor, patch(
            "src.api.ogc_api.services.generate_bim_modells.BoreholesGenericApp"
        ) as mock_app:

            mock_fetch.return_value = object()
            mock_processor.return_value.parse.return_value = records
            mock_app.build_ifc.return_value = "/path/to/boreholes.ifc"

            task = execute_generate_boreholes_model.delay(
                valid_boreholes_request_params.model_dump()
            )
            result = task.get(timeout=10)

            mock_fetch.assert_called_once()
            mock_processor.assert_called_once_with()
            mock_processor.return_value.parse.assert_called_once()
            mock_app.build_ifc.assert_called_once()

            assert mock_app.build_ifc.call_args.args[0] == records
            assert result["model"]["filename"].startswith("Baugrundaufschluesse_")
            assert result["model"]["content_type"] == "application/x-step"

    def test_boreholes_model_without_xml(self, valid_boreholes_request_params):
        with patch(
            "src.api.ogc_api.services.generate_bim_modells.DataFetcher.fetch_borehole_data"
        ) as mock_fetch:
            mock_fetch.return_value = None

            with pytest.raises(ValueError, match=NO_BOREHOLE_DATA_MESSAGE):
                task = execute_generate_boreholes_model.delay(
                    valid_boreholes_request_params.model_dump()
                )
                task.get(timeout=10)

    def test_boreholes_model_empty_umring(self, valid_boreholes_request_params):
        with patch(
            "src.api.ogc_api.services.generate_bim_modells.DataFetcher.fetch_borehole_data"
        ) as mock_fetch, patch(
            "src.api.ogc_api.services.generate_bim_modells.BoreholeMLProcessor"
        ) as mock_processor:
            mock_fetch.return_value = object()
            mock_processor.return_value.parse.return_value = []

            task = execute_generate_boreholes_model.delay(
                valid_boreholes_request_params.model_dump()
            )
            result = task.get(timeout=10)

            assert result["model"] is None
            assert result["message"] == NO_BOREHOLES_MESSAGE

    def test_boreholes_model_ifc_write_failure(self, valid_boreholes_request_params):
        with patch(
            "src.api.ogc_api.services.generate_bim_modells.DataFetcher.fetch_borehole_data"
        ) as mock_fetch, patch(
            "src.api.ogc_api.services.generate_bim_modells.BoreholeMLProcessor"
        ) as mock_processor, patch(
            "src.api.ogc_api.services.generate_bim_modells.BoreholesGenericApp"
        ) as mock_app:

            mock_fetch.return_value = object()
            mock_processor.return_value.parse.return_value = _sample_records()
            mock_app.build_ifc.return_value = None

            with pytest.raises(ValueError, match=BOREHOLES_IFC_FAILED_MESSAGE):
                task = execute_generate_boreholes_model.delay(
                    valid_boreholes_request_params.model_dump()
                )
                task.get(timeout=10)

    def test_boreholes_model_umring_too_large(self, valid_boreholes_request_params):
        params = valid_boreholes_request_params.model_copy(deep=True)
        params.bbox.max_x = params.bbox.min_x + 0.1
        params.bbox.max_y = params.bbox.min_y + 0.1

        with pytest.raises(ValueError, match=BOREHOLES_AREA_LIMIT_MESSAGE):
            task = execute_generate_boreholes_model.delay(params.model_dump())
            task.get(timeout=10)

    def test_boreholes_model_exception_handling(self, valid_boreholes_request_params):
        with patch(
            "src.api.ogc_api.services.generate_bim_modells.DataFetcher.fetch_borehole_data"
        ) as mock_fetch:
            mock_fetch.side_effect = Exception("WFS unreachable")

            with pytest.raises(ValueError, match=UNEXPECTED_ERROR_MESSAGE):
                task = execute_generate_boreholes_model.delay(
                    valid_boreholes_request_params.model_dump()
                )
                task.get(timeout=10)
