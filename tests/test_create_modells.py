from BIMFabrikHH.pydantic_models.params_bbox import BoundingBoxParams
from BIMFabrikHH.pydantic_models.params_tree import ModelParams

from src.api.ogc_api.services.UUID_dict import process_jobs
from src.api.ogc_api.services.build_bim_modells import execute_generate_tree_model, execute_generate_city_model
from src.api.ogc_api.services.get_trees import execute_get_trees
from src.api.ogc_api.models.ogc_models import JobStatus

job_id = "d3ac548b-a98b-4ff4-a367-31b17b637cec"
bbox = BoundingBoxParams()

input_data = ModelParams(
    bbox=bbox,
    level_of_geom=2,
    project_name="My Project",
    site_name="My Site",
)

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
    execute_get_trees(job_id, input_data)
    print(f"Status: {process_jobs[job_id].status}")
    print(f"Message: {process_jobs[job_id].message}")
    # print(f"Results: {process_jobs[job_id].results}")


def run_test_build_trees_model():
    execute_generate_tree_model(job_id, input_data)
    print(f"Status: {process_jobs[job_id].status}")
    print(f"Message: {process_jobs[job_id].message}")
    print(f"Results: {process_jobs[job_id].results}")


def run_test_build_city_model():
    execute_generate_city_model(job_id, input_data)
    print(f"Status: {process_jobs[job_id].status}")
    print(f"Message: {process_jobs[job_id].message}")
    print(f"Results: {process_jobs[job_id].results}")


print("Running test: Get Trees")
# run_test_get_trees()
print("Get Trees: Successful\n")

print("Running test: Build Trees Model")
# run_test_build_trees_model()
print("Trees Model: Successful\n")

print("Running test: Build City Model")
run_test_build_city_model()
print("City Model: Successful\n")
