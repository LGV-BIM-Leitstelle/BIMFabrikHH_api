import datetime

from BIMFabrikHH.apps.baum.app import BaumModeller
from BIMFabrikHH.apps.dgm.app import process_terrain_folder_to_ifc
from BIMFabrikHH.apps.stadtmodell.app import process_gml_to_ifc
from BIMFabrikHH.core.folder_utils import check_folder_exists
from BIMFabrikHH.core.request_oaf import HamburgOGCAPI
from BIMFabrikHH.pydantic_models.params_tree import RequestParams
from fastapi import HTTPException

from ..models.ogc_models import JobStatus
from ..utils.ifc_filemanager import save_ifc_file_on_server
from .UUID_dict import process_jobs

baum_modeller = BaumModeller()


def update_job_status(job_id, **kwargs):
    job = process_jobs[job_id]
    for key, value in kwargs.items():
        if value is not None:
            setattr(job, key, value)


def execute_generate_tree_model(job_id: str, input_data: RequestParams):
    try:
        update_job_status(job_id, status=JobStatus.running, started=datetime.datetime.now().isoformat(), progress=50)

        ifc_bytes = baum_modeller.create_tree_model(input_data)
        filename, url = save_ifc_file_on_server(ifc_bytes, "Baeume", job_id)

        update_job_status(
            job_id,
            status=JobStatus.successful,
            progress=100,
            finished=datetime.datetime.now().isoformat(),
            results={
                "model": {
                    "filename": filename,
                    "content_type": "application/x-step",
                    "url": url,
                }
            },
        )

    except Exception as e:
        update_job_status(
            job_id,
            status=JobStatus.failed,
            finished=datetime.datetime.now().isoformat(),
            message=f"Error generating tree model: {str(e)}",
        )


def execute_generate_city_model(job_id: str, input_data: RequestParams):
    try:
        update_job_status(job_id, status=JobStatus.running, started=datetime.datetime.now().isoformat(), progress=25)

        x1 = input_data.bbox.min_x
        y1 = input_data.bbox.min_y
        x2 = input_data.bbox.max_x
        y2 = input_data.bbox.max_y

        gml_files = HamburgOGCAPI.get_tiles(x1, y1, x2, y2, model_type="citymodel")
        print(gml_files)

        if len(gml_files) > 4:
            raise HTTPException(
                status_code=400,
                detail="Anzahl der Kacheln überschreitet die Grenze von 4 Kacheln. "
                "Bitte wählen Sie einen Umring erneut.",
            )

        folder = check_folder_exists("LoD1-DE_HH_2023-04-01")

        ifc_bytes = process_gml_to_ifc(gml_files, input_data, reset_model=True, folder_path=folder)

        update_job_status(job_id, progress=75)

        filename, url = save_ifc_file_on_server(ifc_bytes, "Stadtmodell", job_id)

        update_job_status(
            job_id,
            status=JobStatus.successful,
            progress=100,
            finished=datetime.datetime.now().isoformat(),
            results={
                "model": {
                    "filename": filename,
                    "content_type": "application/x-step",
                    "url": url,
                }
            },
        )

    except Exception as e:
        update_job_status(
            job_id,
            status=JobStatus.failed,
            finished=datetime.datetime.now().isoformat(),
            message=f"Error generating city model: {str(e)}",
        )


def execute_generate_dgm_model(job_id: str, input_data: RequestParams):
    try:
        update_job_status(job_id, status=JobStatus.running, started=datetime.datetime.now().isoformat(), progress=25)

        x1 = input_data.bbox.min_x
        y1 = input_data.bbox.min_y
        x2 = input_data.bbox.max_x
        y2 = input_data.bbox.max_y

        tif_files = HamburgOGCAPI.get_tiles(x1, y1, x2, y2, model_type="dgm")

        print(tif_files)

        if len(tif_files) > 4:
            raise HTTPException(
                status_code=400,
                detail="Anzahl der Kacheln überschreitet die Grenze von 4 Kacheln. "
                "Bitte wählen Sie einen Umring erneut.",
            )

        folder = check_folder_exists("dgm_hamburg")

        # Process the folder and create the IFC file
        ifc_bytes = process_terrain_folder_to_ifc(folder, tif_files)

        update_job_status(job_id, progress=75)

        filename, url = save_ifc_file_on_server(ifc_bytes, "DGM", job_id)

        update_job_status(
            job_id,
            status=JobStatus.successful,
            progress=100,
            finished=datetime.datetime.now().isoformat(),
            results={
                "model": {
                    "filename": filename,
                    "content_type": "application/x-step",
                    "url": url,
                }
            },
        )

    except Exception as e:
        update_job_status(
            job_id,
            status=JobStatus.failed,
            finished=datetime.datetime.now().isoformat(),
            message=f"Error generating DGM model: {str(e)}",
        )
