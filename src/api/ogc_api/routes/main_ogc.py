import datetime
from uuid import uuid4

from BIMFabrikHH.pydantic_models.params_tree import RequestParams
from fastapi import APIRouter, BackgroundTasks, Body, HTTPException
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from src.api.ogc_api.config.dict_conformance import content_conformance
from src.api.ogc_api.config.dict_landing_page import content_landing_page
from src.api.ogc_api.config.dict_processes import content_get_processes
from src.api.ogc_api.config.process_definitions import (
    content_get_process_generate_city_model,
    content_get_process_generate_tree_model,
    content_get_process_get_trees,
)
from src.api.ogc_api.models.ogc_models import JobStatus, ProcessJob
from src.api.ogc_api.services.build_bim_modells import execute_generate_city_model, execute_generate_tree_model
from src.api.ogc_api.services.get_trees import execute_get_trees
from src.api.ogc_api.services.UUID_dict import process_jobs

router_ogc = APIRouter()


PROCESS_INPUT_MODELS = {
    "get-trees": RequestParams,
    "generate-tree-model": RequestParams,
}


# Landing Page
@router_ogc.get(
    "/",
    tags=["Capabilities"],
    summary="Get Landing Page",
    description="Landing page of the BIMFabrikHH OGC API - Processes.",
)
def get_landing_page():
    return JSONResponse(content=content_landing_page)


# Conformance Declaration
@router_ogc.get(
    "/conformance",
    tags=["ConformanceDeclaration"],
    summary="information about standards that this API conforms to",
    description="Returns information about the conformance classes supported by this API.",
)
def get_conformance():
    return JSONResponse(content=content_conformance)


# Process List
@router_ogc.get(
    "/processes",
    tags=["ProcessList"],
    summary="retrieve the list of available processes",
    description="Returns a list of available processes that can be executed.",
)
def get_processes():
    return JSONResponse(content=content_get_processes)


# Process Description
@router_ogc.get(
    "/processes/{processID}",
    tags=["ProcessDescription"],
    summary="Get Process",
    description="Returns the description and input/output schema of a specific process.",
)
def get_process(processID: str):
    if processID == "get-trees":
        return JSONResponse(content=content_get_process_get_trees)
    elif processID == "generate-tree-model":
        return JSONResponse(content=content_get_process_generate_tree_model)
    elif processID == "generate-city-model":
        return JSONResponse(content=content_get_process_generate_city_model)
    else:
        raise HTTPException(status_code=404, detail=f"Process {processID} not found")


# Job List
@router_ogc.get(
    "/jobs", tags=["JobList"], summary="Get Jobs", description="Returns a list of submitted jobs and their metadata."
)
def get_jobs():
    return JSONResponse(content={"jobs": list(process_jobs.values())})


# Execute
@router_ogc.post(
    "/processes/{processID}/execution",
    tags=["Execute"],
    status_code=201,
    summary="Execute Process",
    description="Executes a specified process with provided input parameters and creates a job.",
)
def execute_process(processID: str, background_tasks: BackgroundTasks, inputs: RequestParams = Body(..., embed=True)):
    jobId = str(uuid4())
    job = ProcessJob(id=jobId, status=JobStatus.accepted, created=datetime.datetime.now().isoformat(), type=processID)
    process_jobs[jobId] = job

    # Check if we have a model for this process
    input_model_cls = PROCESS_INPUT_MODELS.get(processID)
    if not input_model_cls:
        raise HTTPException(status_code=404, detail=f"Process {processID} not found")

    try:
        parsed_inputs = inputs
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())

    # Dispatch to the correct handler
    if processID == "get-trees":
        background_tasks.add_task(execute_get_trees, jobId, parsed_inputs)
    elif processID == "generate-tree-model":
        background_tasks.add_task(execute_generate_tree_model, jobId, parsed_inputs)
    elif processID == "generate-city-model":
        background_tasks.add_task(execute_generate_city_model, jobId, parsed_inputs)

    return JSONResponse(content=job.model_dump(), headers={"Location": f"/processes/{processID}/jobs/{jobId}"})


# Job Status
@router_ogc.get(
    "/jobs/{jobId}",
    tags=["Status"],
    summary="Get Job Status",
    description="Returns the status and metadata of a specific job.",
)
def get_job_status(jobId: str):
    job = process_jobs.get(jobId)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JSONResponse(content=job.model_dump())


# Cancel Job
@router_ogc.delete(
    "/jobs/{jobId}",
    tags=["Dismiss"],
    summary="Cancel Job",
    description="Cancels or deletes a job by its ID. Applicable to running or completed jobs.",
)
def cancel_job(jobId: str):
    if jobId in process_jobs:
        del process_jobs[jobId]
        return JSONResponse(content={"message": "Job deleted"})
    raise HTTPException(status_code=404, detail="Job not found")


# Get Job Results
@router_ogc.get(
    "/jobs/{jobId}/results",
    tags=["Result"],
    summary="Get Job Results",
    description="Returns the results of a successfully executed job.",
)
def get_job_results(jobId: str):
    job = process_jobs.get(jobId)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {jobId} not found")

    if job.status != JobStatus.successful:
        raise HTTPException(status_code=404, detail=f"Results not available. Job status: {job.status}")

    # Determine processID from the job type (assuming it's part of the job's metadata)
    processID = job.type  # This assumes the job contains a 'type' field indicating the process

    if processID == "get-trees":
        return JSONResponse(content=job.results["trees"])
    elif processID == "generate-tree-model":
        model_data = job.results["model"]
        return JSONResponse(content={"url": model_data["url"]})
    elif processID == "generate-city-model":
        model_data = job.results["model"]
        return JSONResponse(content={"url": model_data["url"]})
    else:
        raise HTTPException(status_code=404, detail=f"Process {processID} not found")
