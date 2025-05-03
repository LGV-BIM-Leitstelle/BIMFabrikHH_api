import datetime
from typing import Any, Dict
from uuid import uuid4

from BIMFabrikHH.apps.baum import BaumModeller, ModelParams
from BIMFabrikHH.core.request_oaf import HamburgOGCAPI
from BIMFabrikHH.default.url_api import PathUrl
from BIMFabrikHH.pydantic_models.params_bbox import BoundingBoxParams
from fastapi import APIRouter, BackgroundTasks, Body, HTTPException, Response
from fastapi.responses import JSONResponse
from src.api.ogc_standards.ogc_json import (
    content_get_process_generate_tree_model, content_get_process_get_trees,
    content_get_processes)
from src.data_models.ogc_models import JobStatus, ProcessInput, ProcessJob

router_trees_ogc = APIRouter(prefix="/processes")
baum_modeller = BaumModeller()

process_jobs = {}


@router_trees_ogc.get("", response_class=JSONResponse, description="List available processes")
def get_processes():
    return JSONResponse(content_get_processes)


@router_trees_ogc.get("/{process_id}", response_class=JSONResponse, description="Get process description")
def get_process(process_id: str):

    if process_id == "get-trees":
        return JSONResponse(content_get_process_get_trees)

    elif process_id == "generate-tree-model":
        return JSONResponse(content_get_process_generate_tree_model)
    else:
        raise HTTPException(status_code=404, detail=f"Process {process_id} not found")


async def execute_get_trees(job_id: str, input_data: Dict[str, Any]):

    try:
        # Update job status to running
        process_jobs[job_id].status = JobStatus.running
        process_jobs[job_id].started = datetime.datetime.now().isoformat()

        bbox = input_data.get("bbox", [9.9733, 53.5544, 9.9756, 53.5556])
        crs = input_data.get("crs", "http://www.opengis.net/def/crs/EPSG/0/25832")
        limit = input_data.get("limit", 2000)
        skip_geometry = input_data.get("skip_geometry", True)

        bbox_str = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"

        url = PathUrl.URL_OAF_TREES
        params_trees = {
            "f": "json",
            "bbox": bbox_str,
            "crs": crs,
            "limit": limit,
            "skipGeometry": str(skip_geometry).lower(),
        }

        # Fetch data
        process_jobs[job_id].progress = 50
        trees_data = HamburgOGCAPI.fetch_data(url, params_trees)

        # Update job with results
        process_jobs[job_id].progress = 100
        process_jobs[job_id].status = JobStatus.successful
        process_jobs[job_id].finished = datetime.datetime.now().isoformat()
        process_jobs[job_id].results = {"trees": trees_data}

    except Exception as e:
        process_jobs[job_id].status = JobStatus.failed
        process_jobs[job_id].finished = datetime.datetime.now().isoformat()
        process_jobs[job_id].message = f"Error fetching tree data: {str(e)}"


async def execute_generate_tree_model(job_id: str, input_data: Dict[str, Any]):
    try:
        # Update job status to running
        process_jobs[job_id].status = JobStatus.running
        process_jobs[job_id].started = datetime.datetime.now().isoformat()

        bbox = input_data.get("bbox", [9.9847, 53.5519, 9.9856, 53.5522])
        level_of_geom = input_data.get("level_of_geom", 1)
        project_name = input_data.get("project_name", "Test")

        # Create model parameters
        params = ModelParams(
            bbox=BoundingBoxParams(
                min_x=bbox[0],
                min_y=bbox[1],
                max_x=bbox[2],
                max_y=bbox[3]
            ),
            level_of_geom=level_of_geom,
            project_name=project_name
        )

        # Generate model
        process_jobs[job_id].progress = 50
        ifc_bytes = baum_modeller.create_trees(params)

        # Update job with results
        process_jobs[job_id].progress = 100
        process_jobs[job_id].status = JobStatus.successful
        process_jobs[job_id].finished = datetime.datetime.now().isoformat()

        # Store the reference to the file in results
        process_jobs[job_id].results = {
            "model": {
                "filename": f"trees_{project_name}.ifc",
                "content_type": "application/x-step",
                "data": ifc_bytes,
            }
        }

    except Exception as e:
        process_jobs[job_id].status = JobStatus.failed
        process_jobs[job_id].finished = datetime.datetime.now().isoformat()
        process_jobs[job_id].message = f"Error generating tree model: {str(e)}"


@router_trees_ogc.post(
    "/{process_id}/execution", response_class=JSONResponse, description="Execute a process", status_code=201
)
async def execute_process(process_id: str, background_tasks: BackgroundTasks, inputs: ProcessInput = Body(...)):

    # Generate job ID
    job_id = str(uuid4())

    # Create job
    job = ProcessJob(
        id=job_id,
        status=JobStatus.accepted,
        created=datetime.datetime.now().isoformat()
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
        headers={"Location": f"/processes/{process_id}/jobs/{job_id}"}
    )


@router_trees_ogc.get("/{process_id}/jobs", response_class=JSONResponse, description="List jobs for a process")
def list_jobs(process_id: str):

    jobs = [job for job in process_jobs.values() if job.type == process_id]
    return JSONResponse(content={"jobs": jobs})


@router_trees_ogc.get("/{process_id}/jobs/{job_id}", response_class=JSONResponse, description="Get job status")
def get_job(job_id: str):

    job_data = process_jobs.get(job_id)

    if job_data is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if isinstance(job_data, bytes):
        return Response(content=job_data, media_type="application/octet-stream")

    return JSONResponse(content=job_data)


@router_trees_ogc.get("/{process_id}/jobs/{job_id}/results", response_class=Response, description="Get job results")
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
            headers={"Content-Disposition": f"attachment; filename={model_data['filename']}"}
        )
    else:
        raise HTTPException(status_code=404, detail=f"Process {process_id} not found")
