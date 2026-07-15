"""
Pytest configuration and shared fixtures.

This module provides common fixtures and configuration for all tests
in the BIMFabrikHH API project.
"""

import os
import sys
from typing import Any, Dict
from unittest.mock import Mock

import pytest
from BIMFabrikHH_core.data_models.params_bbox import BoundingBoxParams
from BIMFabrikHH_core.data_models.params_tree import Component, Container
from BIMFabrikHH_core.data_models.params_tree import RequestParams as TreeRequestParams

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


# Global fixtures
@pytest.fixture(scope="session")
def project_root_path():
    """Get the project root path."""
    return project_root


@pytest.fixture(scope="session")
def test_data_dir():
    """Get the test data directory."""
    return os.path.join(project_root, "tests", "test_data")


# Mock fixtures
@pytest.fixture
def mock_celery_task():
    """Create a mock Celery task for testing."""
    task = Mock()
    task.request.id = "test-task-123"
    task.update_state = Mock()
    return task


@pytest.fixture
def mock_celery_task_with_id():
    """Create a mock Celery task with custom ID."""

    def _create_task(task_id: str = "test-task-123"):
        task = Mock()
        task.request.id = task_id
        task.update_state = Mock()
        return task

    return _create_task


@pytest.fixture
def celery_eager_mode():
    """Run Celery tasks eagerly (in-process) without a worker or broker.

    Enabling ``task_always_eager`` executes ``.delay()`` calls synchronously in
    the current process, and ``task_eager_propagates`` re-raises task
    exceptions from ``.get()``. This removes the need for a running Celery
    worker or a live broker/result backend (Redis or SQLite) during tests.
    """
    from src.api.ogc_api.services.generate_bim_modells import app

    prev_always = app.conf.task_always_eager
    prev_propagates = app.conf.task_eager_propagates
    app.conf.task_always_eager = True
    app.conf.task_eager_propagates = True
    try:
        yield app
    finally:
        app.conf.task_always_eager = prev_always
        app.conf.task_eager_propagates = prev_propagates


# Data fixtures
@pytest.fixture
def valid_bbox_data():
    """Valid bounding box data for Hamburg area."""
    return {"min_x": 9.9756, "min_y": 53.5522, "max_x": 9.9789, "max_y": 53.5536}


@pytest.fixture
def valid_input_data(valid_bbox_data):
    """Valid input data for model generation."""
    return {
        "bbox": valid_bbox_data,
        "containers": [
            {
                "containerTitle": "Tree Information",
                "containerId": "tree_data",
                "components": {
                    "species": {"title": "Tree Species", "value": "Oak"},
                    "height": {"title": "Tree Height", "value": 15.5},
                },
            }
        ],
    }


@pytest.fixture
def valid_tree_request_params():
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
    return TreeRequestParams(
        bbox=BoundingBoxParams(
            min_x=9.9756, min_y=53.5522, max_x=9.9789, max_y=53.5536
        ),
        containers=[container],
    )


@pytest.fixture
def valid_city_request_params():
    container = Container(
        containerTitle="City Information",
        containerId="city_data",
        components={
            "building_type": Component(title="Building Type", value="Residential"),
            "height": Component(title="Building Height", value=25.0),
        },
    )
    return TreeRequestParams(
        bbox=BoundingBoxParams(
            min_x=9.9756, min_y=53.5522, max_x=9.9789, max_y=53.5536
        ),
        containers=[container],
    )


@pytest.fixture
def valid_dgm_request_params():
    container = Container(
        containerTitle="Terrain Information",
        containerId="terrain_data",
        components={
            "resolution": Component(title="Terrain Resolution", value="1m"),
            "elevation": Component(title="Elevation Range", value="0-100m"),
        },
    )
    return TreeRequestParams(
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


@pytest.fixture
def sample_city_tiles():
    """Sample city model tiles for testing."""
    return ["LoD1_32_565_5932_1_HH.xml", "LoD1_32_566_5932_1_HH.xml"]


@pytest.fixture
def sample_dgm_tiles():
    """Sample DGM tiles for testing."""
    return ["dgm1_32_565_5932_1_hh_2022.tif", "dgm1_32_566_5932_1_hh_2022.tif"]


@pytest.fixture
def sample_ifc_content():
    """Sample IFC content for testing."""
    return b"ISO-10303-21;\nHEADER;\nFILE_DESCRIPTION(('IFC file'),'2;1');\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;"


# Mock dependency fixtures
@pytest.fixture
def mock_data_fetcher(sample_tree_data, sample_city_tiles, sample_dgm_tiles):
    """Create a mock DataFetcher for testing."""
    mock_fetcher = Mock()
    mock_fetcher.fetch_tree_data.return_value = sample_tree_data
    mock_fetcher.fetch_citymodel_tiles.return_value = sample_city_tiles
    mock_fetcher.fetch_dgm_tiles.return_value = sample_dgm_tiles
    return mock_fetcher


@pytest.fixture
def mock_baum_modeller():
    """Create a mock BaumModeller for testing."""
    mock_baum = Mock()
    mock_baum.create_tree_model.return_value = "/tmp/test_tree_model.ifc"
    return mock_baum


@pytest.fixture
def mock_file_saver():
    """Create a mock file saver for testing."""
    mock_save = Mock()
    mock_save.return_value = (
        "test_model.ifc",
        "http://localhost/test_model.ifc",
        "https://localhost/test_model.ifc",
    )
    return mock_save


@pytest.fixture
def mock_processors(sample_ifc_content):
    """Create mock processors for testing."""
    return {
        "process_gml_to_ifc": Mock(return_value=sample_ifc_content),
        "process_terrain_folder_to_ifc": Mock(return_value=sample_ifc_content),
        "check_folder_exists": Mock(return_value="/path/to/test/folder"),
    }


# Test data fixtures
@pytest.fixture
def invalid_inputs():
    """Various invalid input data for testing."""
    return [
        {"invalid": "data"},
        {"bbox": "not_a_dict"},
        {"bbox": {"min_x": "not_a_number"}},
        {},
        {"bbox": {"min_x": 0.0, "min_y": 0.0, "max_x": 0.0, "max_y": 0.0}},
        {"bbox": {"min_x": 1.0, "min_y": 1.0, "max_x": 1.0, "max_y": 1.0}},
        {"bbox": {"min_x": -1.0, "min_y": -1.0, "max_x": -1.0, "max_y": -1.0}},
    ]


@pytest.fixture
def too_many_tiles_scenarios():
    """Scenarios with too many tiles for testing."""
    return {
        "city_tiles": [
            ["file1.xml", "file2.xml", "file3.xml", "file4.xml", "file5.xml"],
            ["file1.xml"] * 10,  # 10 files
            [
                "file1.xml",
                "file2.xml",
                "file3.xml",
                "file4.xml",
                "file5.xml",
                "file6.xml",
            ],  # 6 files
        ],
        "dgm_tiles": [
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
    }


# Test validation helpers
@pytest.fixture
def validate_model_result():
    """Validate that a model generation result has the correct structure."""

    def _validate(result: Dict[str, Any]) -> bool:
        if not isinstance(result, dict):
            return False

        if "model" not in result:
            return False

        model = result["model"]
        required_fields = ["filename", "content_type", "url-http", "url-https"]

        return all(field in model for field in required_fields)

    return _validate


@pytest.fixture
def validate_progress_updates():
    """Validate that task progress updates were called correctly."""

    def _validate(mock_task: Mock, expected_percentages: list | None = None) -> bool:
        if expected_percentages is None:
            expected_percentages = [0, 25, 50, 75, 100]

        calls = mock_task.update_state.call_args_list
        progress_calls = [call for call in calls if call[0][0] == "PROGRESS"]

        if len(progress_calls) < len(expected_percentages):
            return False

        actual_percentages = [call[1]["meta"]["percent"] for call in progress_calls]

        return all(percent in actual_percentages for percent in expected_percentages)

    return _validate


# Test markers
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests (fast, isolated)")
    config.addinivalue_line(
        "markers", "integration: Integration tests (slower, with external dependencies)"
    )
    config.addinivalue_line("markers", "slow: Slow tests (performance tests)")
    config.addinivalue_line("markers", "tree: Tests for tree model generation")
    config.addinivalue_line("markers", "city: Tests for city model generation")
    config.addinivalue_line("markers", "dgm: Tests for DGM model generation")
    config.addinivalue_line("markers", "celery: Tests for Celery task functionality")
    config.addinivalue_line("markers", "error: Error handling tests")
    config.addinivalue_line(
        "markers",
        "external_api: Live integration tests against Hamburg OGC API URLs from .env",
    )


# Test collection hooks
def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test names."""
    for item in items:
        # Add markers based on test class names
        if "TreeModel" in item.name:
            item.add_marker(pytest.mark.tree)
        elif "CityModel" in item.name:
            item.add_marker(pytest.mark.city)
        elif "DGMModel" in item.name:
            item.add_marker(pytest.mark.dgm)
        elif "Celery" in item.name:
            item.add_marker(pytest.mark.celery)

        # Add error marker for exception tests
        if "exception" in item.name.lower() or "error" in item.name.lower():
            item.add_marker(pytest.mark.error)

        # Add unit marker by default (unless already marked)
        if not any(item.iter_markers()):
            item.add_marker(pytest.mark.unit)
