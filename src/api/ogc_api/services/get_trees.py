import datetime

from BIMFabrikHH.core.request_oaf import HamburgOGCAPI
from BIMFabrikHH.default.url_api import PathUrl
from BIMFabrikHH.pydantic_models.params_tree import RequestParams

from ..models.ogc_models import JobStatus
from .UUID_dict import process_jobs


def execute_get_trees(job_id: str, input_data: RequestParams):
    try:
        process_jobs[job_id].status = JobStatus.running
        process_jobs[job_id].started = datetime.datetime.now().isoformat()

        bbox = input_data.bbox

        url = PathUrl.URL_OAF_TREES
        params_trees = {
            "f": "json",
            "bbox": f"{bbox.min_x},{bbox.min_y},{bbox.max_x},{bbox.max_y}",
            "crs": "http://www.opengis.net/def/crs/EPSG/0/25832",
            "limit": 2000,
            "skipGeometry": "false",
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
