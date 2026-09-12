"""
Tests for Flurstueck (cadastral parcel) model generation functionality.

Tasks run in Celery eager mode (see the ``celery_eager_mode`` fixture in
conftest.py), so ``.delay()``/``.get()`` execute in-process without a running
worker or broker. Heavy core dependencies are mocked.
"""

from unittest.mock import patch

import pytest

from src.api.ogc_api.services.generate_bim_modells import (
    execute_generate_flurstuecke_model,
)
from src.api.ogc_api.utils.user_messages import (
    AREA_LIMIT_MESSAGE,
    FLURSTUECKE_IFC_FAILED_MESSAGE,
    NO_FLURSTUECK_DATA_MESSAGE,
    NO_FLURSTUECKE_MESSAGE,
    UNEXPECTED_ERROR_MESSAGE,
)

# Integration-style tests that exercise the full task in eager mode.
pytestmark = [pytest.mark.integration, pytest.mark.celery, pytest.mark.flurstueck]


@pytest.fixture(autouse=True)
def _enable_eager(celery_eager_mode):
    """Run all tasks in this module eagerly (no worker/broker required)."""
    yield


class TestFlurstueckeModelGeneration:
    """Tests for Flurstuecke model generation."""

    def test_successful_flurstuecke_model_generation(
        self, valid_flurstuecke_request_params, sample_flurstueck_data
    ):
        """A parcel in the umring yields an IFC download payload."""
        with patch(
            "src.api.ogc_api.services.generate_bim_modells.HamburgOGCAPI.fetch_all_features"
        ) as mock_fetch, patch(
            "src.api.ogc_api.services.generate_bim_modells.FlurstueckeGenericApp"
        ) as mock_app:

            mock_fetch.return_value = sample_flurstueck_data
            mock_app.build_ifc.return_value = "/path/to/flurstuecke.ifc"

            task = execute_generate_flurstuecke_model.delay(
                valid_flurstuecke_request_params.model_dump()
            )
            result = task.get(timeout=10)

            mock_fetch.assert_called_once()
            mock_app.build_ifc.assert_called_once()

            # The records handed to the app come from the fetched features.
            records = mock_app.build_ifc.call_args.args[0]
            assert len(records) == len(sample_flurstueck_data["features"])
            assert records[0].gemarkung == "Altstadt Nord"

            assert result["model"]["filename"].startswith("Flurstuecke_")
            assert result["model"]["content_type"] == "application/x-step"

    def test_flurstuecke_model_without_features_key(
        self, valid_flurstuecke_request_params
    ):
        """A response that is not a feature collection is a data error."""
        with patch(
            "src.api.ogc_api.services.generate_bim_modells.HamburgOGCAPI.fetch_all_features"
        ) as mock_fetch:
            mock_fetch.return_value = {"foo": "bar"}

            with pytest.raises(ValueError, match=NO_FLURSTUECK_DATA_MESSAGE):
                task = execute_generate_flurstuecke_model.delay(
                    valid_flurstuecke_request_params.model_dump()
                )
                task.get(timeout=10)

    def test_flurstuecke_model_empty_umring(self, valid_flurstuecke_request_params):
        """An empty feature collection succeeds with a message and no model."""
        with patch(
            "src.api.ogc_api.services.generate_bim_modells.HamburgOGCAPI.fetch_all_features"
        ) as mock_fetch:
            mock_fetch.return_value = {
                "type": "FeatureCollection",
                "features": [],
            }

            task = execute_generate_flurstuecke_model.delay(
                valid_flurstuecke_request_params.model_dump()
            )
            result = task.get(timeout=10)

            assert result["model"] is None
            assert result["message"] == NO_FLURSTUECKE_MESSAGE

    def test_flurstuecke_model_ifc_write_failure(
        self, valid_flurstuecke_request_params, sample_flurstueck_data
    ):
        """A ``None`` from the app is reported as a generation failure."""
        with patch(
            "src.api.ogc_api.services.generate_bim_modells.HamburgOGCAPI.fetch_all_features"
        ) as mock_fetch, patch(
            "src.api.ogc_api.services.generate_bim_modells.FlurstueckeGenericApp"
        ) as mock_app:

            mock_fetch.return_value = sample_flurstueck_data
            mock_app.build_ifc.return_value = None

            with pytest.raises(ValueError, match=FLURSTUECKE_IFC_FAILED_MESSAGE):
                task = execute_generate_flurstuecke_model.delay(
                    valid_flurstuecke_request_params.model_dump()
                )
                task.get(timeout=10)

    def test_flurstuecke_model_umring_too_large(self, valid_flurstuecke_request_params):
        """The shared 1 km² umring cap is enforced before any fetch."""
        params = valid_flurstuecke_request_params.model_copy(deep=True)
        params.bbox.max_x = params.bbox.min_x + 0.1
        params.bbox.max_y = params.bbox.min_y + 0.1

        with pytest.raises(ValueError, match=AREA_LIMIT_MESSAGE):
            task = execute_generate_flurstuecke_model.delay(params.model_dump())
            task.get(timeout=10)

    def test_flurstuecke_model_exception_handling(
        self, valid_flurstuecke_request_params
    ):
        """An unexpected fetch error is mapped to the generic user message."""
        with patch(
            "src.api.ogc_api.services.generate_bim_modells.HamburgOGCAPI.fetch_all_features"
        ) as mock_fetch:
            mock_fetch.side_effect = Exception("OAF unreachable")

            with pytest.raises(ValueError, match=UNEXPECTED_ERROR_MESSAGE):
                task = execute_generate_flurstuecke_model.delay(
                    valid_flurstuecke_request_params.model_dump()
                )
                task.get(timeout=10)
