"""
Test configuration and fixtures for BIM model generation tests.

This module provides common test data, mock objects, and configuration
for testing the generate_bim_modells.py module.
"""

from typing import Any, Dict
from unittest.mock import Mock

# Test data fixtures
VALID_BBOX_DATA = {"min_x": 9.9756, "min_y": 53.5522, "max_x": 9.9789, "max_y": 53.5536}

VALID_INPUT_DATA = {
    "bbox": VALID_BBOX_DATA,
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

SAMPLE_TREE_DATA = {
    "features": [
        {
            "geometry": {"type": "Point", "coordinates": [9.976, 53.553]},
            "properties": {"baumart": "Oak", "hoehe": 15.5},
        },
        {
            "geometry": {"type": "Point", "coordinates": [9.977, 53.554]},
            "properties": {"baumart": "Maple", "hoehe": 12.0},
        },
    ]
}

SAMPLE_CITY_TILES = ["LoD1_32_565_5932_1_HH.xml", "LoD1_32_566_5932_1_HH.xml"]

SAMPLE_DGM_TILES = ["dgm1_32_565_5932_1_hh_2022.tif", "dgm1_32_566_5932_1_hh_2022.tif"]

SAMPLE_IFC_CONTENT = b"ISO-10303-21;\nHEADER;\nFILE_DESCRIPTION(('IFC file'),'2;1');\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;"


def create_mock_celery_task(task_id: str = "test-task-123") -> Mock:
    """
    Create a mock Celery task for testing.

    Args:
        task_id: Task ID for the mock task

    Returns:
        Mock Celery task object
    """
    mock_task = Mock()
    mock_task.request.id = task_id
    mock_task.update_state = Mock()
    return mock_task


def create_mock_data_fetcher() -> Mock:
    """
    Create a mock DataFetcher for testing.

    Returns:
        Mock DataFetcher object
    """
    mock_fetcher = Mock()
    mock_fetcher.fetch_tree_data.return_value = SAMPLE_TREE_DATA
    mock_fetcher.fetch_citymodel_tiles.return_value = SAMPLE_CITY_TILES
    mock_fetcher.fetch_dgm_tiles.return_value = SAMPLE_DGM_TILES
    return mock_fetcher


def create_mock_baum_modeller() -> Mock:
    """
    Create a mock BaumModeller for testing.

    Returns:
        Mock BaumModeller object
    """
    mock_baum = Mock()
    mock_baum.create_tree_model.return_value = "/tmp/test_tree_model.ifc"
    return mock_baum


def create_mock_file_saver() -> Mock:
    """
    Create a mock file saver for testing.

    Returns:
        Mock file saver object
    """
    mock_save = Mock()
    mock_save.return_value = (
        "test_model.ifc",
        "http://localhost/test_model.ifc",
        "https://localhost/test_model.ifc",
    )
    return mock_save


def create_mock_processors() -> Dict[str, Mock]:
    """
    Create mock processors for testing.

    Returns:
        Dictionary of mock processor objects
    """
    return {
        "process_gml_to_ifc": Mock(return_value=SAMPLE_IFC_CONTENT),
        "process_terrain_folder_to_ifc": Mock(return_value=SAMPLE_IFC_CONTENT),
        "check_folder_exists": Mock(return_value="/path/to/test/folder"),
    }


# Test scenarios
TEST_SCENARIOS = {
    "successful_tree_generation": {
        "input": VALID_INPUT_DATA,
        "expected_result": {
            "model": {
                "filename": "test_model.ifc",
                "content_type": "application/x-step",
                "url-http": "http://localhost/test_model.ifc",
                "url-https": "https://localhost/test_model.ifc",
            }
        },
    },
    "too_many_tiles": {
        "input": VALID_INPUT_DATA,
        "tiles": ["file1.xml", "file2.xml", "file3.xml", "file4.xml", "file5.xml"],
        "expected_exception": "ValueError",
        "expected_message": "Anzahl der Kacheln überschreitet die Grenze",
    },
    "no_file_path": {
        "input": VALID_INPUT_DATA,
        "baum_return_value": None,
        "expected_exception": "ValueError",
        "expected_message": "Tree model generation returned no file path",
    },
    "network_error": {
        "input": VALID_INPUT_DATA,
        "fetcher_exception": Exception("Network error"),
        "expected_exception": "Exception",
        "expected_message": "Network error",
    },
}


# Test validation helpers
def validate_model_result(result: Dict[str, Any]) -> bool:
    """
    Validate that a model generation result has the correct structure.

    Args:
        result: Result dictionary from model generation

    Returns:
        True if result is valid, False otherwise
    """
    if not isinstance(result, dict):
        return False

    if "model" not in result:
        return False

    model = result["model"]
    required_fields = ["filename", "content_type", "url-http", "url-https"]

    return all(field in model for field in required_fields)


def validate_progress_updates(
    mock_task: Mock, expected_percentages: list | None = None
) -> bool:
    """
    Validate that task progress updates were called correctly.

    Args:
        mock_task: Mock Celery task
        expected_percentages: List of expected percentage values

    Returns:
        True if progress updates are valid, False otherwise
    """
    if expected_percentages is None:
        expected_percentages = [0, 25, 50, 75, 100]

    calls = mock_task.update_state.call_args_list
    progress_calls = [call for call in calls if call[0][0] == "PROGRESS"]

    if len(progress_calls) < len(expected_percentages):
        return False

    actual_percentages = [call[1]["meta"]["percent"] for call in progress_calls]

    return all(percent in actual_percentages for percent in expected_percentages)
