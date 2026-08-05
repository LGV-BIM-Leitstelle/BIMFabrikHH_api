"""
Tests for DGM model generation functionality.

Tasks run in Celery eager mode (see the ``celery_eager_mode`` fixture in
conftest.py), so ``.delay()``/``.get()`` execute in-process without a running
worker or broker. Heavy core dependencies are mocked.
"""

from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from src.api.ogc_api.services.generate_bim_modells import execute_generate_dgm_model

# Integration-style tests that exercise the full task in eager mode.
pytestmark = [pytest.mark.integration, pytest.mark.celery, pytest.mark.dgm]


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
    """Valid input data for DGM model generation."""
    return {
        "bbox": {"min_x": 9.9756, "min_y": 53.5522, "max_x": 9.9789, "max_y": 53.5536},
        "containers": [
            {
                "containerTitle": "Terrain Information",
                "containerId": "terrain_data",
                "components": {
                    "resolution": {"title": "Terrain Resolution", "value": "1m"},
                    "elevation": {"title": "Elevation Range", "value": "0-100m"},
                },
            }
        ],
    }


@pytest.fixture
def sample_dgm_tiles():
    """Sample DGM tiles for testing."""
    return ["dgm1_32_565_5932_1_hh_2022.tif", "dgm1_32_566_5932_1_hh_2022.tif"]


@pytest.fixture
def sample_ifc_content():
    """Sample IFC content for testing."""
    return b"ISO-10303-21;\nHEADER;\nFILE_DESCRIPTION(('IFC file'),'2;1');\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;"


class TestDGMModelGeneration:
    """Tests for DGM model generation."""

    def test_successful_dgm_model_generation(
        self, valid_dgm_request_params, sample_dgm_tiles, sample_ifc_content
    ):
        """Test successful DGM model generation."""
        with patch(
            "src.api.ogc_api.services.generate_bim_modells.DataFetcher"
        ) as mock_fetcher_class, patch(
            "src.api.ogc_api.services.generate_bim_modells.TerrainGenericApp"
        ) as mock_app:

            # Mock dependencies
            mock_fetcher_class.fetch_dgm_tiles.return_value = sample_dgm_tiles
            mock_app.from_geotiffs.return_value = "/path/to/dgm_model.ifc"

            # Execute task (runs eagerly in-process)
            task = execute_generate_dgm_model.delay(
                valid_dgm_request_params.model_dump()
            )
            result = task.get(timeout=10)

            # Verify result structure
            mock_app.from_geotiffs.assert_called_once()
            assert "model" in result
            assert result["model"]["filename"].startswith("DGM_")
            assert result["model"]["content_type"] == "application/x-step"

    @pytest.mark.parametrize(
        "too_many_tiles",
        [
            ["file1.tif", "file2.tif", "file3.tif", "file4.tif", "file5.tif"],
            ["file1.tif"] * 8,  # 8 files
            [
                "file1.tif",
                "file2.tif",
                "file3.tif",
                "file4.tif",
                "file5.tif",
                "file6.tif",
            ],  # 6 files
        ],
    )
    def test_dgm_model_too_many_tiles(self, valid_dgm_request_params, too_many_tiles):
        """Test DGM model generation with too many tiles."""
        with patch(
            "src.api.ogc_api.services.generate_bim_modells.DataFetcher"
        ) as mock_fetcher_class:
            # Mock dependency to return too many tiles
            mock_fetcher_class.fetch_dgm_tiles.return_value = too_many_tiles

            # Execute task and expect ValueError
            with pytest.raises(
                ValueError, match="Anzahl der Kacheln überschreitet die Grenze"
            ):
                task = execute_generate_dgm_model.delay(
                    valid_dgm_request_params.model_dump()
                )
                task.get(timeout=10)

    def test_dgm_model_exception_handling(self, valid_dgm_request_params):
        """Test DGM model generation exception handling."""
        with patch(
            "src.api.ogc_api.services.generate_bim_modells.DataFetcher"
        ) as mock_fetcher_class:
            # Mock dependency to raise exception
            mock_fetcher_class.fetch_dgm_tiles.side_effect = Exception(
                "Terrain processing error"
            )

            # Execute task and expect failure
            with pytest.raises(Exception, match="Terrain processing error"):
                task = execute_generate_dgm_model.delay(
                    valid_dgm_request_params.model_dump()
                )
                task.get(timeout=10)


class TestDGMModelIntegration:
    """Integration tests for DGM model generation."""

    @pytest.mark.integration
    def test_dgm_model_integration(
        self, valid_dgm_request_params, sample_dgm_tiles, sample_ifc_content
    ):
        """Integration test for DGM model generation with mocked external dependencies."""
        with patch(
            "src.api.ogc_api.services.generate_bim_modells.DataFetcher"
        ) as mock_fetcher_class, patch(
            "src.api.ogc_api.services.generate_bim_modells.TerrainGenericApp"
        ) as mock_app:

            # Mock external dependencies
            mock_fetcher_class.fetch_dgm_tiles.return_value = sample_dgm_tiles
            mock_app.from_geotiffs.return_value = "/path/to/terrain_data/dgm_model.ifc"

            # Execute task
            task = execute_generate_dgm_model.delay(
                valid_dgm_request_params.model_dump()
            )
            result = task.get(timeout=10)

            # Verify integration
            mock_fetcher_class.fetch_dgm_tiles.assert_called_once()
            mock_app.from_geotiffs.assert_called_once()

            # Verify result
            assert "model" in result
            assert result["model"]["filename"].startswith("DGM_")
