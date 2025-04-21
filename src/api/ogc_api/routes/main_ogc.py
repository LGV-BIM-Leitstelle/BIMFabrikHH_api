import datetime
from uuid import uuid4

from BIMFabrikHH.pydantic_models.params_tree import ModelParams
from fastapi import FastAPI, APIRouter, BackgroundTasks, HTTPException, Body
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from src.api.ogc_api.config.dict_conformance import content_conformance
from src.api.ogc_api.config.dict_landing_page import content_landing_page
from src.api.ogc_api.config.dict_processes import content_get_processes
from src.api.ogc_api.config.process_definitions import (
    content_get_process_generate_tree_model,
    content_get_process_get_trees,
    content_get_process_generate_city_model,
)
from src.api.ogc_api.models.ogc_models import ProcessJob, JobStatus
from src.api.ogc_api.services.UUID_dict import process_jobs
from src.api.ogc_api.services.build_bim_modells import execute_generate_tree_model, execute_generate_city_model
from src.api.ogc_api.services.get_trees import execute_get_trees

# Routers
router_ogc_landingpage = APIRouter(prefix="")
router_ogc_conformance = APIRouter(prefix="/conformance")
router_ogc_processes = APIRouter(prefix="/processes")
router_ogc_joblist = APIRouter(prefix="/jobs")
router_ogc_status = APIRouter(prefix="/status")
router_ogc_result = APIRouter(prefix="/result")

PROCESS_INPUT_MODELS = {
    "get-trees": ModelParams,
    "generate-tree-model": ModelParams,
}


# Landing Page
@router_ogc_landingpage.get(
    "/",
    tags=["Capabilities"],
    summary="Get Landing Page",
    description="Landing page of the BIMFabrikHH OGC API - Processes.",
)
def get_landing_page():
    return JSONResponse(content=content_landing_page)


# Conformance Declaration
@router_ogc_conformance.get(
    "",
    tags=["ConformanceDeclaration"],
    summary="information about standards that this API conforms to",
    description="Returns information about the conformance classes supported by this API.",
)
def get_conformance():
    return JSONResponse(content=content_conformance)


# Process List
@router_ogc_processes.get(
    "",
    tags=["ProcessList"],
    summary="retrieve the list of available processes",
    description="Returns a list of available processes that can be executed.",
)
def get_processes():
    return JSONResponse(content=content_get_processes)


# Process Description
@router_ogc_processes.get(
    "/{process_id}",
    tags=["ProcessDescription"],
    summary="Get Process",
    description="Returns the description and input/output schema of a specific process.",
)
def get_process(process_id: str):
    if process_id == "get-trees":
        return JSONResponse(content=content_get_process_get_trees)
    elif process_id == "generate-tree-model":
        return JSONResponse(content=content_get_process_generate_tree_model)
    elif process_id == "generate-city-model":
        return JSONResponse(content=content_get_process_generate_city_model)
    else:
        raise HTTPException(status_code=404, detail=f"Process {process_id} not found")


# Job List
@router_ogc_joblist.get(
    "", tags=["JobList"], summary="Get Jobs", description="Returns a list of submitted jobs and their metadata."
)
def get_jobs():
    return JSONResponse(content={"jobs": list(process_jobs.values())})


# Execute Process
# @router_ogc_joblist.post(
#     "/{process_id}/execution",
#     tags=["Execute"],
#     status_code=201,
#     summary="Execute Process",
#     description="Executes a specified process with provided input parameters and creates a job.",
# )
# async def execute_process(process_id: str, background_tasks: BackgroundTasks, inputs: ModelParams = Body(...)):
#     job_id = str(uuid4())
#     job = ProcessJob(id=job_id, status=JobStatus.accepted, created=datetime.datetime.now().isoformat(), type=process_id)
#     process_jobs[job_id] = job
#
#     if process_id == "get-trees":
#         background_tasks.add_task(execute_get_trees, job_id, inputs)
#     elif process_id == "generate-tree-model":
#         background_tasks.add_task(execute_generate_tree_model, job_id, inputs.model_dump())
#     else:
#         raise HTTPException(status_code=404, detail=f"Process {process_id} not found")
#
#     return JSONResponse(content=job.model_dump(), headers={"Location": f"/processes/{process_id}/jobs/{job_id}"})


@router_ogc_joblist.post("/processes/{process_id}/execution")
async def execute_process(
    process_id: str,
    background_tasks: BackgroundTasks,
    inputs: ModelParams = Body(..., embed=True),  # embed=True keeps the JSON body as an object, not nested
):
    job_id = str(uuid4())
    job = ProcessJob(
        id=job_id,
        status=JobStatus.accepted,
        created=datetime.datetime.now().isoformat(),
        type=process_id,
    )
    process_jobs[job_id] = job

    # Check if we have a model for this process
    input_model_cls = PROCESS_INPUT_MODELS.get(process_id)
    if not input_model_cls:
        raise HTTPException(status_code=404, detail=f"Process {process_id} not found")

    try:
        parsed_inputs = inputs
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())

    # Dispatch to the correct handler
    if process_id == "get-trees":
        background_tasks.add_task(execute_get_trees, job_id, parsed_inputs)
    elif process_id == "generate-tree-model":
        background_tasks.add_task(execute_generate_tree_model, job_id, parsed_inputs)
    elif process_id == "generate-city-model":
        background_tasks.add_task(execute_generate_city_model, job_id, parsed_inputs)

    return JSONResponse(content=job.model_dump(), headers={"Location": f"/processes/{process_id}/jobs/{job_id}"})


# Job Status
@router_ogc_status.get(
    "/{process_id}/jobs/{job_id}",
    tags=["Status"],
    summary="Get Job Status",
    description="Returns the status and metadata of a specific job.",
)
def get_job_status(job_id: str):
    job = process_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JSONResponse(content=job.model_dump())


# Cancel Job
@router_ogc_status.delete(
    "/{process_id}/jobs/{job_id}",
    tags=["Dismiss"],
    summary="Cancel Job",
    description="Cancels or deletes a job by its ID. Applicable to running or completed jobs.",
)
def cancel_job(job_id: str):
    if job_id in process_jobs:
        del process_jobs[job_id]
        return JSONResponse(content={"message": "Job deleted"})
    raise HTTPException(status_code=404, detail="Job not found")


# Get Job Results
@router_ogc_result.get(
    "/{process_id}/jobs/{job_id}/results",
    tags=["Result"],
    summary="Get Job Results",
    description="Returns the results of a successfully executed job.",
)
def get_job_results(process_id: str, job_id: str):
    if job_id not in process_jobs:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    job = process_jobs[job_id]
    if job.status != JobStatus.successful:
        raise HTTPException(status_code=404, detail=f"Results not available. Job status: {job.status}")

    if process_id == "get-trees":
        return JSONResponse(content=job.results["trees"])
    elif process_id == "generate-tree-model":
        model_data = job.results["model"]
        return JSONResponse(content={"url": model_data["url"]})
    elif process_id == "generate-city-model":
        model_data = job.results["model"]
        return JSONResponse(content={"url": model_data["url"]})
    else:
        raise HTTPException(status_code=404, detail=f"Process {process_id} not found")


if __name__ == "__main__":
    app = FastAPI(
        title="BIMFabrikHH OGC API - Processes",
        description="A sample API conforming to the OGC API - Processes - Part 1 standard.\n\n"
        "This API allows the execution of spatial and building-related processes "
        "(e.g. IFC model creation from GIS data).",
        version="1.0.0",
    )

    app.include_router(router_ogc_landingpage)
    app.include_router(router_ogc_conformance)
    app.include_router(router_ogc_processes)
    app.include_router(router_ogc_joblist)
    app.include_router(router_ogc_status)
    app.include_router(router_ogc_result)

    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8004)
