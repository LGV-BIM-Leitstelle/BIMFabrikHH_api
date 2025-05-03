from BIMFabrikHH.apps.baum.app import BaumModeller
from BIMFabrikHH.pydantic_models.params_bbox import BoundingBoxParams
from BIMFabrikHH.pydantic_models.params_tree import ModelParams, ProjectInfos, RequestParams
from src.api.ogc_api.models.ogc_models import JobStatus
from src.api.ogc_api.services.build_bim_modells import (
    execute_generate_city_model,
    execute_generate_dgm_model,
    execute_generate_tree_model,
)
from src.api.ogc_api.services.get_trees import execute_get_trees
from src.api.ogc_api.services.UUID_dict import process_jobs

job_id = "d3ac548b-a98b-4ff4-a367-31b17b637cec"

baum_modeller = BaumModeller()

bbox_params = BoundingBoxParams(min_x=9.9664, min_y=53.5517, max_x=9.9764, max_y=53.5572)

model_params = ModelParams(
    project_info=ProjectInfos(project_name="Test_MyProject", site_name="Test_MySite"), level_of_geom=4
)

request_body = RequestParams(bbox=bbox_params, model_params=model_params)


# Mock job state
process_jobs[job_id] = type(
    "MockJob",
    (),
    {
        "status": JobStatus.accepted,
        "progress": 0,
        "started": None,
        "finished": None,
        "results": None,
        "message": None,
    },
)()


def run_test_get_trees():
    execute_get_trees(job_id, request_body)
    print(f"Status: {process_jobs[job_id].status}")
    print(f"Message: {process_jobs[job_id].message}")
    print(f"Results: {process_jobs[job_id].results}")


def run_test_build_trees_model():
    execute_generate_tree_model(job_id, request_body)
    print(f"Status: {process_jobs[job_id].status}")
    print(f"Message: {process_jobs[job_id].message}")
    print(f"Results: {process_jobs[job_id].results}")


def run_test_build_city_model():
    execute_generate_city_model(job_id, request_body)
    print(f"Status: {process_jobs[job_id].status}")
    print(f"Message: {process_jobs[job_id].message}")
    print(f"Results: {process_jobs[job_id].results}")


def run_test_build_dgm_model():
    execute_generate_dgm_model(job_id, request_body)
    print(f"Status: {process_jobs[job_id].status}")
    print(f"Message: {process_jobs[job_id].message}")
    print(f"Results: {process_jobs[job_id].results}")


print("Running test: Get Trees")
run_test_get_trees()
print("Get Trees: Successful\n")

print("Running test: Build Trees Model")
run_test_build_trees_model()
print("Trees Model: Successful\n")

print("Running test: Build City Model")
run_test_build_city_model()
print("City Model: Successful\n")

print("Running test: Build DGM Model")
run_test_build_dgm_model()
print("DGM Model: Successful\n")
