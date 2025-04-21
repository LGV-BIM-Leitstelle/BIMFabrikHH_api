import datetime
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Body, HTTPException
from fastapi.responses import JSONResponse, Response

from src.api.ogc_api.config.dict_conformance import content_conformance
from src.api.ogc_api.config.dict_landing_page import content_landing_page
from src.api.ogc_api.config.process_definitions import (
    content_get_processes,
    content_get_process_generate_tree_model,
    content_get_process_get_trees,
)
from src.api.ogc_api.services.job_service import process_jobs
from src.api.ogc_api.services.generate_trees import execute_generate_tree_model
from src.api.ogc_api.services.tree_service import execute_get_trees

# from src.api.ogc_standards.ogc_json import content_get_process_get_trees
from src.data_models.ogc_models import ProcessInput, ProcessJob, JobStatus


# Landing page (Capabilities)
router_ogc_landingpage = APIRouter(prefix="", tags=["Capabilities"])  # OK: root should be empty, not "/"

# Conformance declaration
router_ogc_conformance = APIRouter(prefix="/conformance", tags=["ConformanceDeclaration"])

# Processes: List and Description
router_ogc_processes = APIRouter(prefix="/processes")

# Job list and execution
router_ogc_joblist = APIRouter(prefix="/jobs", tags=["JobList", "Execute"])

# Job status
router_ogc_status = APIRouter(prefix="/status", tags=["Status"])

# Job result
router_ogc_result = APIRouter(prefix="/result", tags=["Result"])


# Landing page route implementation
@router_ogc_landingpage.get("/", response_class=JSONResponse, description="Landing page")
def get_landing_page():
    return JSONResponse(content=content_landing_page)


# Conformance declaration route implementation
@router_ogc_conformance.get("", response_class=JSONResponse, description="Conformance declaration")
def get_conformance():
    return JSONResponse(content=content_conformance)


# Jobs list route implementation
@router_ogc_joblist.get("", response_class=JSONResponse, description="List all jobs")
def get_jobs():
    all_jobs = list(process_jobs.values())
    return JSONResponse(content={"jobs": all_jobs})


@router_ogc_processes.get("", response_class=JSONResponse, description="List available processes", tags=["ProcessList"])
def get_processes():
    return JSONResponse(content=content_get_processes)


@router_ogc_processes.get(
    "/{process_id}", response_class=JSONResponse, description="Get process description", tags=["ProcessDescription"]
)
def get_process(process_id: str):
    if process_id == "get-trees":
        return JSONResponse(content=content_get_process_get_trees)
    elif process_id == "generate-tree-model":
        return JSONResponse(content=content_get_process_generate_tree_model)
    else:
        raise HTTPException(status_code=404, detail=f"Process {process_id} not found")


@router_ogc_joblist.post(
    "/{process_id}/execution", response_class=JSONResponse, description="Execute a process", status_code=201
)
async def execute_process(process_id: str, background_tasks: BackgroundTasks, inputs: ProcessInput = Body(...)):

    job_id = str(uuid4())

    # Create job
    job = ProcessJob(
        id=job_id,
        status=JobStatus.accepted,
        created=datetime.datetime.now().isoformat(),
    )

    # Store job
    process_jobs[job_id] = job

    if process_id == "get-trees":
        background_tasks.add_task(execute_get_trees, job_id, inputs)
    elif process_id == "generate-tree-model":
        background_tasks.add_task(execute_generate_tree_model, job_id, inputs)
    else:
        raise HTTPException(status_code=404, detail=f"Process {process_id} not found")

    return JSONResponse(
        status_code=201,
        content=job.model_dump(),
        headers={"Location": f"/processes/{process_id}/jobs/{job_id}"},
    )


@router_ogc_status.get(
    "/{process_id}/jobs/{job_id}", response_class=JSONResponse, description="retrieve the status of a job"
)
def get_job(job_id: str):
    job_data = process_jobs.get(job_id)

    if job_data is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if isinstance(job_data, bytes):
        return Response(content=job_data, media_type="application/octet-stream")

    return JSONResponse(content=job_data.model_dump())


@router_ogc_joblist.get("/{process_id}/jobs", response_class=JSONResponse, description="List jobs for a process")
def list_jobs(process_id: str):
    jobs = [job for job in process_jobs.values() if job.type == process_id]
    return JSONResponse(content={"jobs": jobs})


@router_ogc_result.get("/{process_id}/jobs/{job_id}/results", response_class=Response, description="Get job results")
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
        return Response(
            content=model_data["data"],
            media_type=model_data["content_type"],
            headers={"Content-Disposition": f"attachment; filename={model_data['filename']}"},
        )
    else:
        raise HTTPException(status_code=404, detail=f"Process {process_id} not found")
