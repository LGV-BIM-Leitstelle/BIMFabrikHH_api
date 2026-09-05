"""
Tests for city model generation functionality.

Tasks run in Celery eager mode (see the ``celery_eager_mode`` fixture in
conftest.py), so ``.delay()``/``.get()`` execute in-process without a running
worker or broker. Heavy core dependencies are mocked.
"""

from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from src.api.ogc_api.services.generate_bim_modells import (
    execute_generate_city_model,
    execute_generate_city_model_rs,
)
from src.api.ogc_api.utils.user_messages import (
    AREA_LIMIT_MESSAGE,
    NO_BUILDINGS_MESSAGE,
    TILE_LIMIT_MESSAGE,
    UNEXPECTED_ERROR_MESSAGE,
)

# Integration-style tests that exercise the full task in eager mode.
pytestmark = [pytest.mark.integration, pytest.mark.celery, pytest.mark.city]


@pytest.fixture(autouse=True)
def _enable_eager(celery_eager_mode):
    """Run all tasks in this module eagerly (no worker/broker required)."""
    yield


@pytest.fixture
def mock_celery_task():
    """Mock Celery task for testing."""
    mock = Mock()
    mock.update_state = Mock()
    mock.request.id = "test-task-id"
    return mock


@pytest.fixture
def valid_input_data():
    """Valid input data for city model generation."""
    return {
        "bbox": {"min_x": 9.9756, "min_y": 53.5522, "max_x": 9.9789, "max_y": 53.5536},
        "containers": [
            {
                "containerTitle": "City Information",
                "containerId": "city_data",
                "components": {
                    "building_type": {"title": "Building Type", "value": "Residential"},
                    "height": {"title": "Building Height", "value": 25.0},
                },
            }
        ],
    }


@pytest.fixture
def sample_city_tiles():
    """Sample city tiles for testing."""
    return ["LoD1_32_565_5932_1_HH.xml", "LoD1_32_566_5932_1_HH.xml"]


@pytest.fixture
def sample_ifc_content():
    """Sample IFC content for testing."""
    return b"ISO-10303-21;\nHEADER;\nFILE_DESCRIPTION(('IFC file'),'2;1');\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;"


class TestCityModelGeneration:
    """Tests for city model generation."""

    def test_successful_city_model_generation(
        self, valid_city_request_params, sample_city_tiles, sample_ifc_content
    ):
        """Test successful city model generation."""
        with patch(
            "src.api.ogc_api.services.generate_bim_modells.DataFetcher"
        ) as mock_fetcher_class, patch(
            "src.api.ogc_api.services.generate_bim_modells.extract_level_of_geometry",
            return_value=1,
        ), patch(
            "src.api.ogc_api.services.generate_bim_modells.transform_file_names_for_lod",
            side_effect=lambda files, lod, folder: files,
        ), patch(
            "src.api.ogc_api.services.generate_bim_modells.CityGenericApp"
        ) as mock_app:

            # Mock dependencies
            mock_fetcher_class.fetch_citymodel_tiles.return_value = sample_city_tiles
            mock_app.from_gml_files.return_value = "/path/to/city_model.ifc"

            # Execute task (runs eagerly in-process)
            task = execute_generate_city_model.delay(
                valid_city_request_params.model_dump()
            )
            result = task.get(timeout=10)

            # Verify result structure
            mock_app.from_gml_files.assert_called_once()
            assert "model" in result
            assert result["model"]["filename"].startswith("Stadtmodell_")
            assert result["model"]["content_type"] == "application/x-step"

    @pytest.mark.parametrize(
        "too_many_tiles",
        [
            [f"file{i}.xml" for i in range(7)],
            ["file1.xml"] * 10,
        ],
    )
    def test_city_model_too_many_tiles(
        self, valid_city_request_params, too_many_tiles, assert_task_failed
    ):
        """Test city model generation with too many tiles."""
        with patch(
            "src.api.ogc_api.services.generate_bim_modells.DataFetcher"
        ) as mock_fetcher_class:
            # Mock dependency to return too many tiles
            mock_fetcher_class.fetch_citymodel_tiles.return_value = too_many_tiles

            # Task records a FAILURE state with a ValueError about the tile limit
            assert_task_failed(
                execute_generate_city_model,
                valid_city_request_params.model_dump(),
                match=TILE_LIMIT_MESSAGE,
                exc_type="ValueError",
            )

    def test_city_model_area_limit(self, valid_city_request_params, assert_task_failed):
        """A bbox larger than 1 km² is rejected before tiles are fetched."""
        payload = valid_city_request_params.model_dump()
        payload["bbox"] = {
            "min_x": 9.96,
            "min_y": 53.54,
            "max_x": 10.00,
            "max_y": 53.56,
        }
        with patch(
            "src.api.ogc_api.services.generate_bim_modells.DataFetcher"
        ) as mock_fetcher_class:
            assert_task_failed(
                execute_generate_city_model,
                payload,
                match=AREA_LIMIT_MESSAGE,
                exc_type="ValueError",
            )
            mock_fetcher_class.fetch_citymodel_tiles.assert_not_called()

    def test_city_model_exception_handling(
        self, valid_city_request_params, assert_task_failed
    ):
        """Test city model generation exception handling."""
        with patch(
            "src.api.ogc_api.services.generate_bim_modells.DataFetcher"
        ) as mock_fetcher_class:
            # Mock dependency to raise exception
            mock_fetcher_class.fetch_citymodel_tiles.side_effect = Exception(
                "Processing error"
            )

            # Task records a FAILURE state carrying the underlying error message
            assert_task_failed(
                execute_generate_city_model,
                valid_city_request_params.model_dump(),
                match=UNEXPECTED_ERROR_MESSAGE,
                exc_type="ValueError",
            )

    def test_city_model_rs_exception_handling(
        self, valid_city_request_params, assert_task_failed
    ):
        """Test city model (rs) generation exception handling."""
        with patch(
            "src.api.ogc_api.services.generate_bim_modells.DataFetcher"
        ) as mock_fetcher_class:
            # Mock dependency to raise exception
            mock_fetcher_class.fetch_citymodel_tiles.side_effect = Exception(
                "Rust error"
            )

            # The exception must propagate so Celery stores a readable failure.
            # Swallowing it into a FAILURE state without exc_type made
            # GET /ogc/jobs/{jobId} answer 500 instead of the job status.
            assert_task_failed(
                execute_generate_city_model_rs,
                valid_city_request_params.model_dump(),
                match=UNEXPECTED_ERROR_MESSAGE,
                exc_type="ValueError",
            )

    def test_city_model_rs_no_buildings_ui_message(
        self, valid_city_request_params, sample_city_tiles, assert_task_failed
    ):
        """Rust empty-parse is mapped to the UI no-buildings message."""
        with patch(
            "src.api.ogc_api.services.generate_bim_modells.DataFetcher"
        ) as mock_fetcher_class, patch(
            "src.api.ogc_api.services.generate_bim_modells.extract_level_of_geometry",
            return_value=3,
        ), patch(
            "src.api.ogc_api.services.generate_bim_modells.transform_file_names_for_lod",
            side_effect=lambda files, lod, folder: files,
        ), patch(
            "src.api.ogc_api.services.generate_bim_modells.gml_paths_for_rust",
            side_effect=lambda files, folder: files,
        ), patch(
            "src.api.ogc_api.services.generate_bim_modells.CityRustApp"
        ) as mock_app:
            mock_fetcher_class.fetch_citymodel_tiles.return_value = sample_city_tiles
            mock_app.from_gml_files.side_effect = RuntimeError(
                "no buildings parsed from CityGML"
            )

            assert_task_failed(
                execute_generate_city_model_rs,
                valid_city_request_params.model_dump(),
                match=NO_BUILDINGS_MESSAGE,
                exc_type="ValueError",
            )


class TestCityModelIntegration:
    """Integration tests for city model generation."""

    @pytest.mark.integration
    def test_city_model_integration(
        self, valid_city_request_params, sample_city_tiles, sample_ifc_content
    ):
        """Integration test for city model generation with mocked external dependencies."""
        with patch(
            "src.api.ogc_api.services.generate_bim_modells.DataFetcher"
        ) as mock_fetcher_class, patch(
            "src.api.ogc_api.services.generate_bim_modells.extract_level_of_geometry",
            return_value=1,
        ), patch(
            "src.api.ogc_api.services.generate_bim_modells.transform_file_names_for_lod",
            side_effect=lambda files, lod, folder: files,
        ), patch(
            "src.api.ogc_api.services.generate_bim_modells.CityGenericApp"
        ) as mock_app:

            # Mock external dependencies
            mock_fetcher_class.fetch_citymodel_tiles.return_value = sample_city_tiles
            mock_app.from_gml_files.return_value = "/path/to/city_data/city_model.ifc"

            # Execute task
            task = execute_generate_city_model.delay(
                valid_city_request_params.model_dump()
            )
            result = task.get(timeout=10)

            # Verify integration
            mock_fetcher_class.fetch_citymodel_tiles.assert_called_once()
            mock_app.from_gml_files.assert_called_once()

            # Verify result
            assert "model" in result
            assert result["model"]["filename"].startswith("Stadtmodell_")
