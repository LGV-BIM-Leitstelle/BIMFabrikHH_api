"""
Tests for tree model generation functionality.

NOTE: These tests use .delay() which requires a running Celery worker.
Skip with: pytest -m "not requires_worker"
"""

from unittest.mock import Mock, patch

import pytest
from BIMFabrikHH_core.data_models.params_bbox import BoundingBoxParams
from BIMFabrikHH_core.data_models.params_tree import (Component, Container,
                                                      RequestParams)

from src.api.ogc_api.services.generate_bim_modells import \
    execute_generate_tree_model

# Mark all tests in this file as integration tests requiring Celery workers
pytestmark = [pytest.mark.integration, pytest.mark.requires_worker, pytest.mark.slow]


@pytest.fixture
def valid_request_params():
    """Valid request parameters for tree model generation."""
    container = Container(
        containerTitle="Trees_Container",
        containerId="trees_standard",
        components={
            "description": Component(
                title="Description", value="Hamburg Trees Component"
            ),
            "type": Component(title="Data Type", value="Tree Inventory"),
        },
    )

    return RequestParams(
        bbox=BoundingBoxParams(
            min_x=9.9756, min_y=53.5522, max_x=9.9789, max_y=53.5536
        ),
        containers=[container],
    )


@pytest.fixture
def sample_tree_data():
    """Sample tree data for testing."""
    return {
        "features": [
            {
                "geometry": {"coordinates": [9.976, 53.553], "type": "Point"},
                "properties": {"baumart": "Oak", "hoehe": 15.5},
            },
            {
                "geometry": {"coordinates": [9.977, 53.554], "type": "Point"},
                "properties": {"baumart": "Maple", "hoehe": 12.0},
            },
        ]
    }


class TestTreeModelGeneration:
    """Tests for tree model generation."""

    def test_successful_tree_model_generation(
        self, valid_request_params, sample_tree_data
    ):
        """Test successful tree model generation."""
        with patch(
            "src.api.ogc_api.services.generate_bim_modells.DataFetcher"
        ) as mock_fetcher_class, patch(
            "src.api.ogc_api.services.generate_bim_modells.baum_modeller"
        ) as mock_baum, patch(
            "src.api.ogc_api.services.generate_bim_modells.save_ifc_file_on_server"
        ) as mock_save:

            # Mock dependencies
            mock_fetcher = Mock()
            mock_fetcher.fetch_tree_data.return_value = sample_tree_data
            mock_fetcher_class.return_value = mock_fetcher

            mock_baum.create_tree_model.return_value = "/path/to/tree_model.ifc"
            mock_save.return_value = (
                "tree_model.ifc",
                "http://example.com/tree_model.ifc",
                "https://example.com/tree_model.ifc",
            )

            # Execute task using the correct pattern
            task = execute_generate_tree_model.delay(valid_request_params.model_dump())
            result = task.get(timeout=10)

            # Verify result structure
            assert "model" in result
            assert result["model"]["filename"].startswith("Baeume_")
            assert result["model"]["content_type"] == "application/x-step"
            assert "url-http" in result["model"]
            assert "url-https" in result["model"]

    def test_tree_model_no_file_path(self, valid_request_params, sample_tree_data):
        """Test tree model generation when no file path is returned."""
        with patch(
            "src.api.ogc_api.services.generate_bim_modells.DataFetcher"
        ) as mock_fetcher_class, patch(
            "src.api.ogc_api.services.generate_bim_modells.baum_modeller"
        ) as mock_baum:

            # Mock dependencies
            mock_fetcher = Mock()
            mock_fetcher.fetch_tree_data.return_value = sample_tree_data
            mock_fetcher_class.return_value = mock_fetcher

            mock_baum.create_tree_model.return_value = None

            # Execute task and expect failure
            task = execute_generate_tree_model.delay(valid_request_params.model_dump())
            with pytest.raises(
                ValueError, match="Tree model generation returned no file path"
            ):
                task.get(timeout=10)

    def test_tree_model_exception_handling(self, valid_request_params):
        """Test tree model generation exception handling."""
        with patch(
            "src.api.ogc_api.services.generate_bim_modells.DataFetcher"
        ) as mock_fetcher_class:
            # Mock dependency to raise exception
            mock_fetcher = Mock()
            mock_fetcher.fetch_tree_data.side_effect = Exception("Network error")
            mock_fetcher_class.return_value = mock_fetcher

            # Execute task and expect failure
            task = execute_generate_tree_model.delay(valid_request_params.model_dump())
            with pytest.raises(Exception, match="Network error"):
                task.get(timeout=10)

    @pytest.mark.parametrize(
        "invalid_input",
        [
            {"invalid": "data"},
            {"bbox": "not_a_dict"},
            {"bbox": {"min_x": "not_a_number"}},
            {},
        ],
    )
    def test_tree_model_invalid_input(self, invalid_input):
        """Test tree model generation with invalid input data."""
        task = execute_generate_tree_model.delay(invalid_input)
        with pytest.raises(Exception):
            task.get(timeout=10)


class TestTreeModelIntegration:
    """Integration tests for tree model generation."""

    @pytest.mark.integration
    def test_tree_model_integration(self, valid_request_params, sample_tree_data):
        """Integration test for tree model generation with mocked external dependencies."""
        with patch(
            "src.api.ogc_api.services.generate_bim_modells.DataFetcher"
        ) as mock_fetcher, patch(
            "src.api.ogc_api.services.generate_bim_modells.baum_modeller"
        ) as mock_baum, patch(
            "src.api.ogc_api.services.generate_bim_modells.save_ifc_file_on_server"
        ) as mock_save:

            # Mock external dependencies
            mock_fetcher.fetch_tree_data.return_value = sample_tree_data
            mock_baum.create_tree_model.return_value = "/tmp/test_tree_model.ifc"
            mock_save.return_value = (
                "test_tree.ifc",
                "http://localhost/test_tree.ifc",
                "https://localhost/test_tree.ifc",
            )

            # Execute task
            task = execute_generate_tree_model.delay(valid_request_params.model_dump())
            result = task.get(timeout=10)

            # Verify integration
            mock_fetcher.fetch_tree_data.assert_called_once()
            mock_baum.create_tree_model.assert_called_once()
            mock_save.assert_called_once()

            # Verify result
            assert "model" in result
            assert result["model"]["filename"] == "test_tree.ifc"


@pytest.mark.slow
def test_task_execution_performance(valid_request_params, sample_tree_data):
    """Test that task execution completes within reasonable time."""
    import time

    with patch(
        "src.api.ogc_api.services.generate_bim_modells.DataFetcher"
    ) as mock_fetcher, patch(
        "src.api.ogc_api.services.generate_bim_modells.baum_modeller"
    ) as mock_baum, patch(
        "src.api.ogc_api.services.generate_bim_modells.save_ifc_file_on_server"
    ) as mock_save:

        # Mock dependencies
        mock_fetcher.fetch_tree_data.return_value = sample_tree_data
        mock_baum.create_tree_model.return_value = "/path/to/tree_model.ifc"
        mock_save.return_value = (
            "tree_model.ifc",
            "http://example.com/tree_model.ifc",
            "https://example.com/tree_model.ifc",
        )

        # Execute task and measure time
        start_time = time.time()
        task = execute_generate_tree_model.delay(valid_request_params.model_dump())
        result = task.get(timeout=10)
        end_time = time.time()

        execution_time = end_time - start_time

        # Verify result
        assert "model" in result

        # Verify performance (should complete within 1 second for mocked dependencies)
        assert (
            execution_time < 1.0
        ), f"Task execution took {execution_time:.2f} seconds, expected < 1.0"
