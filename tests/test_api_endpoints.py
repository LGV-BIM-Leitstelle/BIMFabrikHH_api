"""
Tests for FastAPI endpoint functionality.

This module tests all HTTP endpoints in the BIMFabrikHH API,
including OGC API Processes routes, Data API routes, and static file serving.
"""

import json
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.web_app import create_app


@pytest.fixture(scope="module")
def client():
    """Create a test client for the FastAPI application."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def valid_execution_input():
    """Valid input data for process execution."""
    return {
        "inputs": {
            "bbox": {
                "min_x": 9.9756,
                "min_y": 53.5522,
                "max_x": 9.9789,
                "max_y": 53.5536
            },
            "containers": [
                {
                    "containerTitle": "Test Container",
                    "containerId": "test_container",
                    "components": {
                        "test_component": {
                            "title": "Test Component",
                            "value": "test value"
                        }
                    }
                }
            ]
        }
    }


class TestMainRoutes:
    """Tests for main application routes."""

    def test_root_endpoint(self, client):
        """Test root endpoint returns HTML landing page."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_root_endpoint_contains_content(self, client):
        """Test root endpoint contains expected HTML content."""
        response = client.get("/")
        assert response.status_code == 200
        # Check for common HTML elements
        content = response.text.lower()
        assert "html" in content or "bimfabrik" in content


class TestOGCAPILandingPage:
    """Tests for OGC API landing page."""

    def test_ogc_landing_page(self, client):
        """Test OGC API landing page endpoint."""
        response = client.get("/ogc/")
        assert response.status_code == 200
        data = response.json()
        
        # OGC API landing page should have links
        assert "links" in data or "title" in data

    def test_ogc_landing_page_content_type(self, client):
        """Test OGC API landing page returns JSON."""
        response = client.get("/ogc/")
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]


class TestProcessesEndpoints:
    """Tests for OGC API Processes endpoints."""

    def test_list_processes(self, client):
        """Test listing all available processes."""
        response = client.get("/ogc/processes")
        assert response.status_code == 200
        
        data = response.json()
        assert "processes" in data
        assert isinstance(data["processes"], list)
        assert len(data["processes"]) > 0

    def test_list_processes_structure(self, client):
        """Test that process list has correct structure."""
        response = client.get("/ogc/processes")
        assert response.status_code == 200
        
        data = response.json()
        processes = data["processes"]
        
        # Check first process has required fields
        first_process = processes[0]
        assert "id" in first_process
        assert "title" in first_process
        assert "description" in first_process
        
    def test_list_processes_contains_expected_processes(self, client):
        """Test that all expected processes are listed."""
        response = client.get("/ogc/processes")
        assert response.status_code == 200
        
        data = response.json()
        process_ids = [p["id"] for p in data["processes"]]
        
        # Check for expected process IDs
        expected_processes = [
            "generate-tree-model",
            "generate-city-model",
            "generate-dgm-model"
        ]
        
        for process_id in expected_processes:
            assert process_id in process_ids, f"Process {process_id} not found"

    def test_get_process_description_tree(self, client):
        """Test getting tree model process description."""
        response = client.get("/ogc/processes/generate-tree-model")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == "generate-tree-model"
        assert "title" in data
        assert "description" in data
        assert "inputs" in data

    def test_get_process_description_city(self, client):
        """Test getting city model process description."""
        response = client.get("/ogc/processes/generate-city-model")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == "generate-city-model"
        assert "title" in data

    def test_get_process_description_dgm(self, client):
        """Test getting DGM model process description."""
        response = client.get("/ogc/processes/generate-dgm-model")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == "generate-dgm-model"
        assert "title" in data

    def test_get_nonexistent_process(self, client):
        """Test getting description for non-existent process."""
        response = client.get("/ogc/processes/nonexistent-process")
        assert response.status_code == 404
        
        data = response.json()
        assert "detail" in data


class TestProcessExecution:
    """Tests for process execution endpoints."""

    @patch('src.api.ogc_api.routes.main_ogc.execute_generate_tree_model')
    def test_execute_tree_model_process(self, mock_task, client, valid_execution_input):
        """Test executing tree model generation process."""
        # Mock Celery task
        mock_result = Mock()
        mock_result.id = "test-task-123"
        mock_task.delay.return_value = mock_result
        
        response = client.post(
            "/ogc/processes/generate-tree-model/execution",
            json=valid_execution_input
        )
        
        assert response.status_code == 201
        assert "Location" in response.headers
        assert "test-task-123" in response.headers["Location"]

    @patch('src.api.ogc_api.routes.main_ogc.execute_generate_city_model')
    def test_execute_city_model_process(self, mock_task, client, valid_execution_input):
        """Test executing city model generation process."""
        mock_result = Mock()
        mock_result.id = "test-task-456"
        mock_task.delay.return_value = mock_result
        
        response = client.post(
            "/ogc/processes/generate-city-model/execution",
            json=valid_execution_input
        )
        
        assert response.status_code == 201
        assert "Location" in response.headers

    @patch('src.api.ogc_api.routes.main_ogc.execute_generate_dgm_model')
    def test_execute_dgm_model_process(self, mock_task, client, valid_execution_input):
        """Test executing DGM model generation process."""
        mock_result = Mock()
        mock_result.id = "test-task-789"
        mock_task.delay.return_value = mock_result
        
        response = client.post(
            "/ogc/processes/generate-dgm-model/execution",
            json=valid_execution_input
        )
        
        assert response.status_code == 201
        assert "Location" in response.headers

    def test_execute_nonexistent_process(self, client, valid_execution_input):
        """Test executing non-existent process."""
        response = client.post(
            "/ogc/processes/nonexistent-process/execution",
            json=valid_execution_input
        )
        
        assert response.status_code == 404

    def test_execute_with_invalid_input_missing_bbox(self, client):
        """Test executing process with missing bbox."""
        invalid_input = {
            "containers": []
        }
        
        response = client.post(
            "/ogc/processes/generate-tree-model/execution",
            json=invalid_input
        )
        
        assert response.status_code == 422  # Validation error

    def test_execute_with_invalid_input_wrong_type(self, client):
        """Test executing process with wrong input type."""
        invalid_input = {
            "bbox": "not_a_dict",
            "containers": []
        }
        
        response = client.post(
            "/ogc/processes/generate-tree-model/execution",
            json=invalid_input
        )
        
        assert response.status_code == 422

    def test_execute_with_empty_body(self, client):
        """Test executing process with empty request body."""
        response = client.post(
            "/ogc/processes/generate-tree-model/execution",
            json={}
        )
        
        assert response.status_code == 422

    def test_execute_without_json_content_type(self, client, valid_execution_input):
        """Test executing process without JSON content type."""
        response = client.post(
            "/ogc/processes/generate-tree-model/execution",
            data=json.dumps(valid_execution_input),
            headers={"Content-Type": "text/plain"}
        )
        
        assert response.status_code in [415, 422]  # Unsupported media type or validation error


class TestJobStatusEndpoints:
    """Tests for job status and results endpoints."""

    @patch('src.api.ogc_api.routes.main_ogc.AsyncResult')
    def test_get_job_status_pending(self, mock_async_result, client):
        """Test getting status of pending job."""
        mock_result = Mock()
        mock_result.state = "PENDING"
        mock_result.info = None
        mock_async_result.return_value = mock_result
        
        response = client.get("/ogc/jobs/test-job-123")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == "test-job-123"
        assert data["status"] == "accepted"

    @patch('src.api.ogc_api.routes.main_ogc.AsyncResult')
    def test_get_job_status_success(self, mock_async_result, client):
        """Test getting status of successful job."""
        mock_result = Mock()
        mock_result.state = "SUCCESS"
        mock_result.result = {"model": {"filename": "test.ifc"}}
        mock_async_result.return_value = mock_result
        
        response = client.get("/ogc/jobs/test-job-456")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == "test-job-456"
        assert data["status"] == "successful"

    @patch('src.api.ogc_api.routes.main_ogc.AsyncResult')
    def test_get_job_status_failed(self, mock_async_result, client):
        """Test getting status of failed job."""
        mock_result = Mock()
        mock_result.state = "FAILURE"
        mock_result.info = Exception("Test error")
        mock_async_result.return_value = mock_result
        
        response = client.get("/ogc/jobs/test-job-789")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == "test-job-789"
        assert data["status"] == "failed"

    @patch('src.api.ogc_api.routes.main_ogc.AsyncResult')
    def test_get_job_results_success(self, mock_async_result, client):
        """Test getting results of successful job."""
        mock_result = Mock()
        mock_result.state = "SUCCESS"
        mock_result.result = {
            "model": {
                "filename": "test_model.ifc",
                "content_type": "application/x-step",
                "url-http": "http://example.com/test_model.ifc",
                "url-https": "https://example.com/test_model.ifc"
            }
        }
        mock_async_result.return_value = mock_result
        
        response = client.get("/ogc/jobs/test-job-success/results")
        assert response.status_code == 200
        
        # API returns URLs directly (not wrapped in "model")
        data = response.json()
        assert "url-http" in data
        assert "url-https" in data
        assert data["url-http"] == "http://example.com/test_model.ifc"

    @patch('src.api.ogc_api.routes.main_ogc.AsyncResult')
    def test_get_job_results_not_ready(self, mock_async_result, client):
        """Test getting results of job that's not finished."""
        mock_result = Mock()
        mock_result.state = "PENDING"
        mock_result.result = None
        mock_async_result.return_value = mock_result
        
        response = client.get("/ogc/jobs/test-job-pending/results")
        assert response.status_code == 404

    @patch('src.api.ogc_api.routes.main_ogc.AsyncResult')
    def test_get_job_results_failed(self, mock_async_result, client):
        """Test getting results of failed job."""
        mock_result = Mock()
        mock_result.state = "FAILURE"
        mock_result.info = Exception("Task failed")
        mock_result.result = None
        mock_async_result.return_value = mock_result
        
        response = client.get("/ogc/jobs/test-job-failed/results")
        # API returns 500 for failed jobs
        assert response.status_code == 500


class TestCORSHeaders:
    """Tests for CORS header configuration."""

    def test_cors_headers_on_get(self, client):
        """Test CORS headers are present on GET requests with Origin."""
        response = client.get(
            "/ogc/processes",
            headers={"Origin": "http://localhost:3000"}
        )
        assert response.status_code == 200
        
        # CORS headers should be present when Origin header is sent
        assert "access-control-allow-origin" in response.headers

    def test_cors_preflight_request(self, client):
        """Test CORS preflight OPTIONS request."""
        response = client.options(
            "/ogc/processes/generate-tree-model/execution",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST"
            }
        )
        
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers


class TestAPIDocumentation:
    """Tests for API documentation endpoints."""

    def test_ogc_docs_endpoint(self, client):
        """Test OGC API documentation endpoint."""
        response = client.get("/ogc/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_ogc_openapi_json(self, client):
        """Test OGC API OpenAPI JSON endpoint."""
        response = client.get("/ogc/openapi.json")
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]
        
        data = response.json()
        assert "openapi" in data
        assert "info" in data
        assert "paths" in data

    def test_data_docs_endpoint(self, client):
        """Test Data API documentation endpoint."""
        response = client.get("/data/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


class TestErrorHandling:
    """Tests for API error handling."""

    def test_404_on_invalid_route(self, client):
        """Test 404 error on invalid route."""
        response = client.get("/invalid/route")
        assert response.status_code == 404

    def test_405_on_wrong_method(self, client):
        """Test 405 error on wrong HTTP method."""
        response = client.put("/ogc/processes")
        assert response.status_code == 405

    def test_invalid_json_body(self, client):
        """Test error handling for invalid JSON."""
        response = client.post(
            "/ogc/processes/generate-tree-model/execution",
            data="invalid json{",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422


class TestInputValidation:
    """Tests for input validation."""

    @pytest.mark.parametrize("invalid_bbox", [
        {"min_x": "not_a_number", "min_y": 53.5, "max_x": 10.0, "max_y": 53.6},
        {"min_x": 9.9, "min_y": 53.5},  # Missing max_x and max_y
        {},  # Empty bbox
        None,  # Null bbox
    ])
    def test_invalid_bounding_box(self, client, invalid_bbox):
        """Test execution with invalid bounding box."""
        invalid_input = {
            "bbox": invalid_bbox,
            "containers": []
        }
        
        response = client.post(
            "/ogc/processes/generate-tree-model/execution",
            json=invalid_input
        )
        
        assert response.status_code == 422

    def test_bounding_box_coordinates_swapped(self, client):
        """Test execution with swapped min/max coordinates."""
        invalid_input = {
            "bbox": {
                "min_x": 10.0,  # Should be less than max_x
                "min_y": 53.6,  # Should be less than max_y
                "max_x": 9.9,
                "max_y": 53.5
            },
            "containers": []
        }
        
        response = client.post(
            "/ogc/processes/generate-tree-model/execution",
            json=invalid_input
        )
        
        # Should either be accepted (if no validation) or rejected
        assert response.status_code in [201, 422]


class TestContentNegotiation:
    """Tests for content negotiation."""

    def test_json_response_default(self, client):
        """Test that JSON is returned by default."""
        response = client.get("/ogc/processes")
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]

    def test_accept_json_header(self, client):
        """Test Accept: application/json header."""
        response = client.get(
            "/ogc/processes",
            headers={"Accept": "application/json"}
        )
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]


@pytest.mark.integration
class TestEndToEndWorkflow:
    """Integration tests for complete workflow."""

    @patch('src.api.ogc_api.routes.main_ogc.execute_generate_tree_model')
    @patch('src.api.ogc_api.routes.main_ogc.AsyncResult')
    def test_complete_tree_model_workflow(
        self, mock_async_result, mock_task, client, valid_execution_input
    ):
        """Test complete workflow from submission to results."""
        # Step 1: Submit job
        mock_submit_result = Mock()
        mock_submit_result.id = "workflow-test-123"
        mock_task.delay.return_value = mock_submit_result
        
        submit_response = client.post(
            "/ogc/processes/generate-tree-model/execution",
            json=valid_execution_input
        )
        assert submit_response.status_code == 201
        
        # Step 2: Check job status
        mock_status_result = Mock()
        mock_status_result.state = "SUCCESS"
        mock_status_result.result = {"model": {"filename": "test.ifc"}}
        mock_async_result.return_value = mock_status_result
        
        status_response = client.get("/ogc/jobs/workflow-test-123")
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "successful"
        
        # Step 3: Get results
        mock_status_result.result = {
            "model": {
                "filename": "test.ifc",
                "content_type": "application/x-step",
                "url-http": "http://example.com/test.ifc",
                "url-https": "https://example.com/test.ifc"
            }
        }
        
        results_response = client.get("/ogc/jobs/workflow-test-123/results")
        assert results_response.status_code == 200
        # API returns URLs directly (not wrapped in "model")
        assert "url-http" in results_response.json()

