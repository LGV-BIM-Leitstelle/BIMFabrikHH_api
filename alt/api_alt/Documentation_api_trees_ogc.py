import datetime
from typing import Dict, Any
from uuid import uuid4

from BIMFabrikHH.apps.baum import BaumModeller, ModelParams
from BIMFabrikHH.core.request_oaf import HamburgOGCAPI
from BIMFabrikHH.default.url_api import PathUrl
from BIMFabrikHH.pydantic_models.params_bbox import BoundingBoxParams
from fastapi import APIRouter, Response, HTTPException, Body, BackgroundTasks
from fastapi.responses import JSONResponse

from src.api.ogc_standards.ogc_json import (
    content_get_processes,
    content_get_process_get_trees,
    content_get_process_generate_tree_model,
)
from src.data_models.ogc_models import JobStatus, ProcessJob, ProcessInput

router_trees_ogc = APIRouter(prefix="/processes")
baum_modeller = BaumModeller()

process_jobs = {}


@router_trees_ogc.get(
    "",
    response_class=JSONResponse,
    description="List available processes",
)
def get_processes():
    """
    Returns a list of available processes that can be executed.

    Available processes include:
    - 'get-trees': Retrieve tree data from the OGC API.
    - 'generate-tree-model': Generate an IFC model of trees within a bounding box.

    Returns:
    - JSONResponse: A list of processes with metadata, including process ID, title, description, and job control options.
    """
    return JSONResponse(content_get_processes)


@router_trees_ogc.get(
    "/{process_id}",
    response_class=JSONResponse,
    description="Get process description",
)
def get_process(process_id: str):
    """
    Retrieves detailed information about a specific process by its process ID.

    This endpoint provides metadata and descriptions of available processes,
    such as 'get-trees' or 'generate-tree-model'. It includes inputs, outputs,
    and job control options for the specified process.

    Parameters:
    - process_id (str): The unique identifier of the process.
      Valid values are 'get-trees' and 'generate-tree-model'.

    Returns:
    - JSONResponse: A JSON object containing process details such as description, inputs, and outputs.

    Raises:
    - HTTPException (404): If the process ID does not exist or is invalid.
    """

    if process_id == "get-trees":
        return JSONResponse(content_get_process_get_trees)

    elif process_id == "generate-tree-model":
        return JSONResponse(content_get_process_generate_tree_model)
    else:
        raise HTTPException(status_code=404, detail=f"Process {process_id} not found")


async def execute_get_trees(job_id: str, input_data: Dict[str, Any]):
    """
    Executes the "get-trees" process to fetch tree data from the OGC API.

    Parameters:
    - job_id (str): The ID of the job.
    - input_data (Dict[str, Any]): The input parameters for the process, including:
        - bbox: Bounding box coordinates (min_x, min_y, max_x, max_y).
        - crs: Coordinate reference system (default: EPSG:25832).
        - limit: Maximum number of trees to return (default: 2000).
        - skip_geometry: Whether to skip geometry in the response (default: True).

    Returns:
    - None: Updates job status and progress, and stores the results in the global `process_jobs` dictionary.
    """

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
                max_y=bbox[3],
            ),
            level_of_geom=level_of_geom,
            project_name=project_name,
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
    "/{process_id}/execution",
    response_class=JSONResponse,
    description="Execute a process",
    status_code=201,
)
async def execute_process(
    process_id: str,
    background_tasks: BackgroundTasks,
    inputs: ProcessInput = Body(...),
):
    """
    Executes a specified process, such as retrieving tree data or generating a tree model.

    The process will run asynchronously, and a job ID is returned to track the status.

    Parameters:
    - process_id (str): The ID of the process to execute. Available processes: 'get-trees', 'generate-tree-model'.
    - background_tasks (BackgroundTasks): FastAPI background task manager for executing the process asynchronously.
    - inputs (Dict[str, Any]): The input data for the process, such as bounding box and parameters for model generation.

    Returns:
    - JSONResponse: A response containing the job ID and initial status.
    """

    # Generate job ID
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


@router_trees_ogc.get(
    "/{process_id}/jobs",
    response_class=JSONResponse,
    description="List jobs for a process",
)
def list_jobs(process_id: str):
    """
    Lists all the jobs associated with a specific process ID.

    This endpoint returns a list of jobs that have been submitted for a specific
    process, such as 'get-trees' or 'generate-tree-model'. It includes information
    about each job, such as its current status, progress, and other job metadata.

    Parameters:
    - process_id (str): The unique identifier of the process.
      Valid values are 'get-trees' and 'generate-tree-model'.

    Returns:
    - JSONResponse: A JSON object containing a list of jobs associated with the specified process.

    Raises:
    - HTTPException (404): If no jobs are found for the specified process ID.
    """

    jobs = [job for job in process_jobs.values() if job.type == process_id]
    return JSONResponse(content={"jobs": jobs})


@router_trees_ogc.get(
    "/{process_id}/jobs/{job_id}",
    response_class=JSONResponse,
    description="Get job status",
)
def get_job(job_id: str):
    """
    Retrieves the status of a specific job.

    Parameters:
    - job_id (str): The ID of the job.

    Returns:
    - JSONResponse: The status of the job, including the job ID, status, progress, and results.
    - HTTPException: If the job is not found, a 404 error is returned.
    """
    job_data = process_jobs.get(job_id)

    if job_data is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if isinstance(job_data, bytes):
        return Response(content=job_data, media_type="application/octet-stream")

    return JSONResponse(content=job_data)


@router_trees_ogc.get(
    "/{process_id}/jobs/{job_id}/results",
    response_class=Response,
    description="Get job results",
)
def get_job_results(process_id: str, job_id: str):
    """
    Retrieves the results of a job after execution.

    This endpoint returns the results of a specific job based on its job ID.
    The job must be in a 'successful' state to fetch the results.

    For the 'get-trees' process, it returns the tree data as GeoJSON.
    For the 'generate-tree-model' process, it returns the generated IFC model file.

    Parameters:
    - process_id (str): The ID of the process for which the job was executed.
      Valid values are 'get-trees' and 'generate-tree-model'.
    - job_id (str): The ID of the job for which to fetch the results.

    Returns:
    - JSONResponse: If the process is 'get-trees', returns the tree data in GeoJSON format.
    - Response: If the process is 'generate-tree-model', returns the generated IFC model file as an attachment with the correct MIME type.

    Raises:
    - HTTPException (404): If the job is not found, or if the job is not in a 'successful' state.
    """

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
