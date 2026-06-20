"""
Tests for DGM model generation functionality.

NOTE: These tests use .delay() which requires a running Celery worker.
Skip with: pytest -m "not requires_worker"
"""

from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from src.api.ogc_api.services.generate_bim_modells import \
    execute_generate_dgm_model

# Mark all tests in this file as integration tests requiring Celery workers
pytestmark = [pytest.mark.integration, pytest.mark.requires_worker, pytest.mark.slow]


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
            "src.api.ogc_api.services.generate_bim_modells.check_folder_exists"
        ) as mock_check, patch(
            "src.api.ogc_api.services.generate_bim_modells.process_terrain_folder_to_ifc"
        ) as mock_process, patch(
            "src.api.ogc_api.services.generate_bim_modells.save_ifc_file_on_server"
        ) as mock_save:

            # Mock dependencies
            mock_fetcher = Mock()
            mock_fetcher.fetch_dgm_tiles.return_value = sample_dgm_tiles
            mock_fetcher_class.return_value = mock_fetcher

            mock_check.return_value = "/path/to/folder"
            mock_process.return_value = sample_ifc_content
            mock_save.return_value = (
                "dgm_model.ifc",
                "http://example.com/dgm_model.ifc",
                "https://example.com/dgm_model.ifc",
            )

            # Execute task using the correct pattern
            task = execute_generate_dgm_model.delay(
                valid_dgm_request_params.model_dump()
            )
            result = task.get(timeout=10)

            # Verify result structure
            assert "model" in result
            assert (
                result["model"]["filename"].startswith("DGM_")
                or result["model"]["filename"] == "dgm_model.ifc"
            )
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
            mock_fetcher = Mock()
            mock_fetcher.fetch_dgm_tiles.return_value = too_many_tiles
            mock_fetcher_class.return_value = mock_fetcher

            # Execute task and expect ValueError
            task = execute_generate_dgm_model.delay(
                valid_dgm_request_params.model_dump()
            )
            with pytest.raises(ValueError, match="Anzahl der Kacheln überschreitet die Grenze"):
                task.get(timeout=10)

    def test_dgm_model_exception_handling(self, valid_dgm_request_params):
        """Test DGM model generation exception handling."""
        with patch(
            "src.api.ogc_api.services.generate_bim_modells.DataFetcher"
        ) as mock_fetcher_class:
            # Mock dependency to raise exception
            mock_fetcher = Mock()
            mock_fetcher.fetch_dgm_tiles.side_effect = Exception(
                "Terrain processing error"
            )
            mock_fetcher_class.return_value = mock_fetcher

            # Execute task and expect failure
            task = execute_generate_dgm_model.delay(
                valid_dgm_request_params.model_dump()
            )
            with pytest.raises(Exception, match="Terrain processing error"):
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
        ) as mock_fetcher, patch(
            "src.api.ogc_api.services.generate_bim_modells.check_folder_exists"
        ) as mock_check, patch(
            "src.api.ogc_api.services.generate_bim_modells.process_terrain_folder_to_ifc"
        ) as mock_process, patch(
            "src.api.ogc_api.services.generate_bim_modells.save_ifc_file_on_server"
        ) as mock_save:

            # Mock external dependencies
            mock_fetcher.fetch_dgm_tiles.return_value = sample_dgm_tiles
            mock_check.return_value = "/path/to/terrain_data"
            mock_process.return_value = sample_ifc_content
            mock_save.return_value = (
                "test_dgm.ifc",
                "http://localhost/test_dgm.ifc",
                "https://localhost/test_dgm.ifc",
            )

            # Execute task
            task = execute_generate_dgm_model.delay(
                valid_dgm_request_params.model_dump()
            )
            result = task.get(timeout=10)

            # Verify integration
            mock_fetcher.fetch_dgm_tiles.assert_called_once()
            mock_check.assert_called_once()
            mock_process.assert_called_once()
            mock_save.assert_called_once()

            # Verify result
            assert "model" in result
            assert result["model"]["filename"] == "test_dgm.ifc"
