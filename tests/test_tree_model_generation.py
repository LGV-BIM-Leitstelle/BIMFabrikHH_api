"""
Tests for tree model generation functionality.

Tasks run in Celery eager mode (see the ``celery_eager_mode`` fixture in
conftest.py), so ``.delay()``/``.get()`` execute in-process without a running
worker or broker. Heavy core dependencies are mocked.
"""

from unittest.mock import Mock, patch

import pytest
from BIMFabrikHH_core.data_models.params_bbox import BoundingBoxParams
from BIMFabrikHH_core.data_models.params_tree import Component, Container, RequestParams

from src.api.ogc_api.services.generate_bim_modells import execute_generate_tree_model

# Integration-style tests that exercise the full task in eager mode.
pytestmark = [pytest.mark.integration, pytest.mark.celery, pytest.mark.tree]


@pytest.fixture(autouse=True)
def _enable_eager(celery_eager_mode):
    """Run all tasks in this module eagerly (no worker/broker required)."""
    yield


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
            "src.api.ogc_api.services.generate_bim_modells.DataProcessor"
        ) as mock_processor, patch(
            "src.api.ogc_api.services.generate_bim_modells.dataframe_to_records"
        ) as mock_to_records, patch(
            "src.api.ogc_api.services.generate_bim_modells.tree_crown_detail_from_containers"
        ), patch(
            "src.api.ogc_api.services.generate_bim_modells.extract_psets_basepoint"
        ) as mock_psets, patch(
            "src.api.ogc_api.services.generate_bim_modells.TreesGenericApp"
        ) as mock_app:

            # Mock dependencies
            mock_fetcher_class.fetch_tree_data.return_value = sample_tree_data
            mock_processor.raw_data_to_dataframe.return_value = Mock(empty=False)
            mock_to_records.return_value = [{"tree": "record"}]
            mock_psets.return_value = []

            # Execute task (runs eagerly in-process)
            task = execute_generate_tree_model.delay(valid_request_params.model_dump())
            result = task.get(timeout=10)

            # Verify the IFC build was invoked and the result structure is correct
            mock_app.build_ifc.assert_called_once()
            assert "model" in result
            assert result["model"]["filename"].startswith("Baeume_")
            assert result["model"]["content_type"] == "application/x-step"
            assert "url-http" in result["model"]
            assert "url-https" in result["model"]

    def test_tree_model_no_trees_found(self, valid_request_params, sample_tree_data):
        """Test tree model generation when no trees are found in the bounding box."""
        with patch(
            "src.api.ogc_api.services.generate_bim_modells.DataFetcher"
        ) as mock_fetcher_class, patch(
            "src.api.ogc_api.services.generate_bim_modells.DataProcessor"
        ) as mock_processor:

            # Data is fetched but the resulting dataframe is empty
            mock_fetcher_class.fetch_tree_data.return_value = sample_tree_data
            mock_processor.raw_data_to_dataframe.return_value = Mock(empty=True)

            # Execute task and expect a ValueError about no trees
            with pytest.raises(ValueError, match="No trees found"):
                task = execute_generate_tree_model.delay(
                    valid_request_params.model_dump()
                )
                task.get(timeout=10)

    def test_tree_model_exception_handling(self, valid_request_params):
        """Test tree model generation exception handling."""
        with patch(
            "src.api.ogc_api.services.generate_bim_modells.DataFetcher"
        ) as mock_fetcher_class:
            # Mock dependency to raise exception
            mock_fetcher_class.fetch_tree_data.side_effect = Exception("Network error")

            # Execute task and expect failure
            with pytest.raises(Exception, match="Network error"):
                task = execute_generate_tree_model.delay(
                    valid_request_params.model_dump()
                )
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
        with pytest.raises(Exception):
            task = execute_generate_tree_model.delay(invalid_input)
            task.get(timeout=10)


class TestTreeModelIntegration:
    """Integration tests for tree model generation."""

    @pytest.mark.integration
    def test_tree_model_integration(self, valid_request_params, sample_tree_data):
        """Integration test for tree model generation with mocked external dependencies."""
        with patch(
            "src.api.ogc_api.services.generate_bim_modells.DataFetcher"
        ) as mock_fetcher_class, patch(
            "src.api.ogc_api.services.generate_bim_modells.DataProcessor"
        ) as mock_processor, patch(
            "src.api.ogc_api.services.generate_bim_modells.dataframe_to_records"
        ) as mock_to_records, patch(
            "src.api.ogc_api.services.generate_bim_modells.tree_crown_detail_from_containers"
        ), patch(
            "src.api.ogc_api.services.generate_bim_modells.extract_psets_basepoint"
        ) as mock_psets, patch(
            "src.api.ogc_api.services.generate_bim_modells.TreesGenericApp"
        ) as mock_app:

            # Mock external dependencies
            mock_fetcher_class.fetch_tree_data.return_value = sample_tree_data
            mock_processor.raw_data_to_dataframe.return_value = Mock(empty=False)
            mock_to_records.return_value = [{"tree": "record"}]
            mock_psets.return_value = []

            # Execute task
            task = execute_generate_tree_model.delay(valid_request_params.model_dump())
            result = task.get(timeout=10)

            # Verify integration
            mock_fetcher_class.fetch_tree_data.assert_called_once()
            mock_app.build_ifc.assert_called_once()

            # Verify result
            assert "model" in result
            assert result["model"]["filename"].startswith("Baeume_")


@pytest.mark.slow
def test_task_execution_performance(valid_request_params, sample_tree_data):
    """Test that task execution completes within reasonable time."""
    import time

    with patch(
        "src.api.ogc_api.services.generate_bim_modells.DataFetcher"
    ) as mock_fetcher_class, patch(
        "src.api.ogc_api.services.generate_bim_modells.DataProcessor"
    ) as mock_processor, patch(
        "src.api.ogc_api.services.generate_bim_modells.dataframe_to_records"
    ) as mock_to_records, patch(
        "src.api.ogc_api.services.generate_bim_modells.tree_crown_detail_from_containers"
    ), patch(
        "src.api.ogc_api.services.generate_bim_modells.extract_psets_basepoint"
    ) as mock_psets, patch(
        "src.api.ogc_api.services.generate_bim_modells.TreesGenericApp"
    ):

        # Mock dependencies
        mock_fetcher_class.fetch_tree_data.return_value = sample_tree_data
        mock_processor.raw_data_to_dataframe.return_value = Mock(empty=False)
        mock_to_records.return_value = [{"tree": "record"}]
        mock_psets.return_value = []

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
