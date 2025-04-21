import datetime
from typing import Dict, Any

from BIMFabrikHH.pydantic_models.params_bbox import BoundingBoxParams
from BIMFabrikHH.pydantic_models.params_tree import ModelParams

from src.api.ogc_api.services.UUID_dict import process_jobs
from src.api.ogc_api.utils.tree_modeller import BaumModeller
from src.data_models.ogc_models import JobStatus

# from models.job import JobStatus
# from models.model_params import ModelParams, BoundingBoxParams
# from services.job_service import process_jobs
# from utils.tree_modeller import BaumModeller

# Initialize the tree modeller
baum_modeller = BaumModeller()


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
