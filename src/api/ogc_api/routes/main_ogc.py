"""
OGC API Processes routes for BIMFabrikHH API.

This module provides OGC API Processes endpoints for executing BIM model generation tasks
including tree models, city models, and digital terrain models.

Copyright (C) 2025 Freie und Hansestadt Hamburg, Landesbetrieb Geoinformation und Vermessung
BIM-Leitstelle, Ahmed Salem <ahmed.salem@gv.hamburg.de>
"""

import datetime

from BIMFabrikHH_core.data_models.params_tree import RequestParams
from celery.result import AsyncResult
from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import JSONResponse

from src.api.ogc_api.ogc_metadata.dict_conformance import content_conformance
from src.api.ogc_api.ogc_metadata.dict_landing_page import content_landing_page
from src.api.ogc_api.ogc_metadata.dict_processes import content_get_processes
from src.api.ogc_api.ogc_metadata.process_definitions import PROCESS_DEFINITIONS
from src.api.ogc_api.services.generate_bim_modells import (
    app,
    execute_generate_city_model,
    execute_generate_city_model_rs,
    execute_generate_dgm_model,
    execute_generate_dgm_model_rs,
    execute_generate_tree_model,
    execute_generate_tree_model_rs,
)
from src.api.config.settings import api_settings

router_ogc = APIRouter()


PROCESS_TASKS = {
    "generate-tree-model": execute_generate_tree_model,
    "generate-city-model": execute_generate_city_model,
    "generate-dgm-model": execute_generate_dgm_model,
    "generate-tree-model-rs": execute_generate_tree_model_rs,
    "generate-city-model-rs": execute_generate_city_model_rs,
    "generate-dgm-model-rs": execute_generate_dgm_model_rs,
}


# Landing Page
@router_ogc.get(
    "/",
    tags=["Capabilities"],
    summary="Get Landing Page",
    description="Landing page of the BIMFabrikHH OGC API - Processes.",
)
def get_landing_page() -> JSONResponse:
    """
    Get the OGC API landing page.

    Returns:
        JSONResponse: Landing page content with API information.
    """
    return JSONResponse(content=content_landing_page)


# Conformance Declaration
@router_ogc.get(
    "/conformance",
    tags=["ConformanceDeclaration"],
    summary="information about standards that this API conforms to",
    description="Returns information about the conformance classes supported by this API.",
)
def get_conformance() -> JSONResponse:
    """
    Get OGC API conformance information.

    Returns:
        JSONResponse: Conformance classes supported by this API.
    """
    return JSONResponse(content=content_conformance)


# Process List
@router_ogc.get(
    "/processes",
    tags=["ProcessList"],
    summary="retrieve the list of available processes",
    description="Returns a list of available processes that can be executed.",
)
def get_processes() -> JSONResponse:
    """
    Get list of available OGC processes.

    Returns:
        JSONResponse: List of available processes that can be executed.
    """
    return JSONResponse(content=content_get_processes)


# Process Description
@router_ogc.get(
    "/processes/{processID}",
    tags=["ProcessDescription"],
    summary="Get Process",
    description="Returns the description and input/output schema of a specific process.",
)
def get_process(processID: str) -> JSONResponse:
    """
    Get description and schema for a specific OGC process.

    Args:
        processID: Identifier of the process to retrieve.

    Returns:
        JSONResponse: Process description and input/output schema.

    Raises:
        HTTPException: If the process is not found.
    """
    description = PROCESS_DEFINITIONS.get(processID)
    if description is None:
        raise HTTPException(status_code=404, detail=f"Process {processID} not found")
    return JSONResponse(content=description)


# Job List
@router_ogc.get(
    "/jobs",
    tags=["JobList"],
    summary="Get Jobs",
    description="Returns a list of submitted jobs and their metadata.",
)
def get_jobs() -> JSONResponse:
    """
    Get list of submitted jobs and their metadata.

    Note: This is a simplified implementation as Celery doesn't provide
    built-in job listing functionality.

    Returns:
        JSONResponse: List of jobs (currently empty as not implemented).
    """
    # Note: Celery doesn't provide a built-in way to list all jobs
    # This is a limitation of the current setup
    # In a production environment, you might want to use a different backend or implement job tracking
    return JSONResponse(
        content={
            "jobs": [],
            "message": "Job listing not implemented with current Celery backend",
        }
    )


# Execute
@router_ogc.post(
    "/processes/{processID}/execution",
    tags=["Execute"],
    status_code=201,
    summary="Execute Process",
    description="Executes a specified process with provided input parameters and creates a job.",
)
def execute_process(
    processID: str, inputs: RequestParams = Body(..., embed=True)
) -> JSONResponse:
    """
    Execute a specified OGC process with provided input parameters.

    Args:
        processID: Identifier of the process to execute.
        inputs: Input parameters for the process.

    Returns:
        JSONResponse: Job information including ID and status.

    Raises:
        HTTPException: If the process is not found.
    """
    task_fn = PROCESS_TASKS.get(processID)
    if task_fn is None:
        raise HTTPException(status_code=404, detail=f"Process {processID} not found")

    task = task_fn.delay(inputs.model_dump())

    jobId = task.id

    # Get base URL from settings
    base_url = str(api_settings.BASE_URL).rstrip('/')

    return JSONResponse(
        status_code=201,
        content={
            "id": jobId,
            "status": "accepted",
            "created": datetime.datetime.now().isoformat(),
            "type": processID,
        },
        headers={"Location": f"{base_url}/ogc/jobs/{jobId}"},
    )


# Job Status
@router_ogc.get(
    "/jobs/{jobId}",
    tags=["Status"],
    summary="Get Job Status",
    description="Returns the status and metadata of a specific job.",
)
def get_job_status(jobId: str) -> JSONResponse:
    """
    Get the status and metadata of a specific job.

    Args:
        jobId: Unique identifier of the job.

    Returns:
        JSONResponse: Job status and metadata information.
    """
    job = AsyncResult(jobId, app=app)

    # Map Celery states to OGC API states
    state_mapping = {
        "PENDING": "accepted",
        "STARTED": "running",
        "SUCCESS": "successful",
        "FAILURE": "failed",
        "REVOKED": "dismissed",
    }

    status = state_mapping.get(job.state, "accepted")

    job_info = {
        "id": jobId,
        "status": status,
        "created": datetime.datetime.now().isoformat(),  # Note: Celery doesn't store creation time
        "type": "process",
    }

    if job.state == "SUCCESS" and job.result:
        job_info["results"] = job.result
    elif job.state == "FAILURE":
        job_info["message"] = str(job.info) if job.info else "Task failed"

    return JSONResponse(content=job_info)


# Cancel Job
@router_ogc.delete(
    "/jobs/{jobId}",
    tags=["Dismiss"],
    summary="Cancel Job",
    description="Cancels or deletes a job by its ID. Applicable to running or completed jobs.",
)
def cancel_job(jobId: str) -> JSONResponse:
    """
    Cancel or delete a job by its ID.

    Args:
        jobId: Unique identifier of the job to cancel.

    Returns:
        JSONResponse: Confirmation message.

    Raises:
        HTTPException: If the job cannot be cancelled.
    """
    job = AsyncResult(jobId, app=app)
    if job.state in ["PENDING", "STARTED"]:
        job.revoke(terminate=True)
        return JSONResponse(content={"message": "Job cancelled"})
    else:
        raise HTTPException(status_code=400, detail="Job cannot be cancelled")


# Get Job Results
@router_ogc.get(
    "/jobs/{jobId}/results",
    tags=["Result"],
    summary="Get Job Results",
    description="Returns the results of a successfully executed job.",
)
def get_job_results(jobId: str) -> JSONResponse:
    """
    Get the results of a successfully executed job.

    Args:
        jobId: Unique identifier of the job.

    Returns:
        JSONResponse: Job results including download URLs.

    Raises:
        HTTPException: If the job failed or is not found.
    """
    job = AsyncResult(jobId, app=app)
    if job.state == "SUCCESS" and job.result:
        model_data = job.result.get("model")
        if model_data:
            return JSONResponse(
                content={
                    "url-http": model_data["url-http"],
                    "url-https": model_data["url-https"],
                }
            )
        else:
            raise HTTPException(status_code=404, detail="No model data found in result")
    elif job.state == "FAILURE":
        raise HTTPException(status_code=500, detail=f"Job failed: {job.info}")
    else:
        raise HTTPException(status_code=404, detail="Job not found or not completed")
