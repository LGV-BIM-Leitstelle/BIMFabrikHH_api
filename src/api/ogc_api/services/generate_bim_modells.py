"""
Service module for generating BIM models.

This module provides Celery tasks for generating different types of BIM models:
- Tree models from cadastral data
- City models from CityGML data
- Digital terrain models (DGM) from GeoTIFF data

Copyright (C) 2025 Freie und Hansestadt Hamburg, Landesbetrieb Geoinformation und Vermessung
BIM-Leitstelle, Ahmed Salem <ahmed.salem@gv.hamburg.de>, Polichronis Muratidis <polichronis.muratidis@gv.hamburg.de>
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from BIMFabrikHH_core import (
    CityGenericApp,
    RequestParams,
    TerrainGenericApp,
    TreesGenericApp,
)
from BIMFabrikHH_core.apps.trees import (
    DEFAULT_OAF_SCHEMA,
    dataframe_to_records,
    tree_crown_detail_from_containers,
)
from BIMFabrikHH_core.core.data_processing import DataProcessor
from BIMFabrikHH_core.core.georeferencing import extract_elevation_df_from_geotiff
from BIMFabrikHH_core.core.ogc_extractor import (
    extract_level_of_geometry,
    extract_psets_basepoint,
)
from celery import Celery, states
from celery.exceptions import Ignore
from celery.signals import task_postrun, task_revoked

from src.api.config.settings import api_settings
from src.database import get_celery_config

from ..utils.lod_utils import transform_file_names_for_lod
from .http_requests import DataFetcher

# Output folder for generated IFC files
OUTPUT_FOLDER = Path(api_settings.OUTPUT_FOLDER_PATH)

logger = logging.getLogger(__name__)

celery_config = get_celery_config()
app = Celery(
    "hamburg", broker=celery_config.broker_url, backend=celery_config.backend_url
)


def _release_admission_slot(task_id: str) -> None:
    """Release the admission-control concurrency slot for a finished task.

    No-op unless admission control is enabled (production/Redis backend).
    Imported lazily so the worker does not require the admission controller (and
    its Redis client) until a task actually completes.
    """
    if not task_id:
        return

    from src.api.config.settings import admission_control_enabled

    if not admission_control_enabled():
        return
    try:
        from .admission_controller import get_admission_controller

        get_admission_controller().release_job(task_id)
    except Exception as e:  # pragma: no cover - cleanup must never crash the worker
        logger.warning("Failed to release admission slot for task %s: %s", task_id, e)


@task_postrun.connect
def _on_task_postrun(task_id: str = None, **kwargs: Any) -> None:
    """Release the concurrency slot after a task succeeds or fails."""
    _release_admission_slot(task_id)


@task_revoked.connect
def _on_task_revoked(request: Any = None, **kwargs: Any) -> None:
    """Release the concurrency slot when a task is revoked/dismissed."""
    task_id = getattr(request, "id", None) if request is not None else None
    _release_admission_slot(task_id)


@app.task(bind=True)
def execute_generate_tree_model(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a BIM model of trees from cadastral data.

    Args:
        self: Celery task instance.
        input_data: Dictionary containing request parameters including bounding box.

    Returns:
        Dict containing model information including download URLs.

    Raises:
        Exception: If model generation fails.
    """
    self.update_state(state="PROGRESS", meta={"percent": 0})

    print("Input data for tree model generation:", input_data)
    try:
        request_params = RequestParams(**input_data)
        bbox = request_params.bbox

        self.update_state(state="PROGRESS", meta={"percent": 25})

        # Convert bbox to dict format for DataFetcher
        bbox_dict = {
            "min_x": bbox.min_x,
            "min_y": bbox.min_y,
            "max_x": bbox.max_x,
            "max_y": bbox.max_y,
        }

        # Fetch raw tree data using API package
        self.update_state(state="PROGRESS", meta={"percent": 50})
        raw_tree_data = DataFetcher.fetch_tree_data(bbox_dict)

        if not raw_tree_data or "features" not in raw_tree_data:
            raise ValueError("No tree data found in the specified bounding box")

        tree_count = len(raw_tree_data.get("features", []))
        print(f"Found {tree_count} trees in the bounding box")

        # Process data using core package
        self.update_state(state="PROGRESS", meta={"percent": 75})

        tif_path = None
        if request_params.use_dgm_elevation:
            tif_filenames = DataFetcher.fetch_dgm_tiles(bbox_dict)
            if not tif_filenames:
                logger.warning(
                    "No terrain data found for the specified bounding box - proceeding without elevation data"
                )
            else:
                dgm_url = f"{api_settings.DATA_BASE_URL}/{api_settings.DATA_DGM_FOLDER}"
                tif_path = f"{dgm_url}/{tif_filenames[0]}"
                logger.info(
                    f"Using GeoTIFF URL for elevation (in-memory processing): {tif_path}"
                )
        else:
            logger.info("Skipping DGM elevation enrichment (use_dgm_elevation=false)")

        # Generate output path for API's output folder
        filename = (
            f"Baeume_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.request.id}.ifc"
        )
        output_path = OUTPUT_FOLDER / filename

        df = DataProcessor.raw_data_to_dataframe(raw_tree_data)
        if df.empty:
            raise ValueError(
                "No trees found in the specified bounding box. Please try a different area or check your coordinates."
            )

        schema = DEFAULT_OAF_SCHEMA
        if tif_path:
            try:
                df = extract_elevation_df_from_geotiff(
                    df,
                    tif_path,
                    schema.easting,
                    schema.northing,
                    schema.elevation,
                )
            except Exception as exc:
                logger.warning("DGM elevation enrichment failed: %s", exc)

        records = dataframe_to_records(
            df,
            aufnahmedatum=datetime.now().strftime("%Y-%m-%d"),
            schema=schema,
            source_name="BIMFabrikHH_api",
            detail=tree_crown_detail_from_containers(request_params.containers),
        )
        if not records:
            raise ValueError(
                "No trees found in the specified bounding box. Please try a different area or check your coordinates."
            )

        basepoint_psets = extract_psets_basepoint(request_params.containers or [])
        TreesGenericApp.build_ifc(
            records,
            output_path=output_path,
            bbox_wgs84=request_params.bbox_as_wgs84_tuple,
            basepoint_psets=basepoint_psets if basepoint_psets else None,
        )

        self.update_state(state="PROGRESS", meta={"percent": 100})

        # File is already saved in the right place - just generate URLs
        url_http = f"{api_settings.URL_OUTPUT_HTTP}/{filename}"
        url_https = f"{api_settings.URL_OUTPUT_HTTPS}/{filename}"

        return {
            "model": {
                "filename": filename,
                "content_type": "application/x-step",
                "url-http": url_http,
                "url-https": url_https,
            }
        }

    except Exception as e:
        self.update_state(
            state=states.FAILURE,
            meta={
                "exc_type": type(e).__name__,
                "exc_message": str(e),
                "error": f"Error generating tree model: {str(e)}",
                "troubleshooting": [
                    "Make sure BIMFabrikHH core package is available",
                    "Check that all dependencies are installed",
                    "Verify internet connection for API calls",
                    "Try a different bounding box area",
                ],
            },
        )
        raise Ignore()


@app.task(bind=True)
def execute_generate_city_model(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a BIM model of buildings from CityGML data.

    Args:
        self: Celery task instance.
        input_data: Dictionary containing request parameters including bounding box.

    Returns:
        Dict containing model information including download URLs.

    Raises:
        ValueError: If too many tiles are requested.
        Exception: If model generation fails.
    """
    self.update_state(state="PROGRESS", meta={"percent": 0})

    try:
        request_params = RequestParams(**input_data)
        bbox = request_params.bbox

        self.update_state(state="PROGRESS", meta={"percent": 25})

        # Convert bbox to dict format for DataFetcher
        bbox_dict = {
            "min_x": bbox.min_x,
            "min_y": bbox.min_y,
            "max_x": bbox.max_x,
            "max_y": bbox.max_y,
        }

        # Fetch tile information using API package
        gml_files = DataFetcher.fetch_citymodel_tiles(bbox_dict)

        if len(gml_files) > 4:
            raise ValueError(
                "Anzahl der Kacheln überschreitet die Grenze von 4 Kacheln. "
                "Bitte wählen Sie einen Umring erneut."
            )

        # Debug: log ALL containers being sent
        containers = request_params.containers or []
        logger.info(f"Received {len(containers)} containers:")
        for container in containers:
            logger.info(f"  - Container: {container.containerId}")

        # Extract LoD from container components using existing core method
        lod_level = extract_level_of_geometry(request_params.containers)
        logger.info(f"Extracted LoD level: {lod_level}")

        # Determine LoD folder URL
        if lod_level == 2:
            lod_folder = api_settings.DATA_LOD2_FOLDER
        else:
            lod_folder = api_settings.DATA_LOD1_FOLDER

        folder_url = f"{api_settings.DATA_BASE_URL}/{lod_folder}"
        logger.info(f"Using LoD{lod_level} directory: {folder_url}")

        self.update_state(state="PROGRESS", meta={"percent": 50})

        # Transform file names if needed
        transformed_gml_files = transform_file_names_for_lod(gml_files, lod_level)
        logger.info(f"Using CityGML tiles: {transformed_gml_files}")

        # Generate output path for API's output folder
        filename = f"Stadtmodell_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.request.id}.ifc"
        output_path = OUTPUT_FOLDER / filename

        ifc_path = CityGenericApp.from_gml_files(
            transformed_gml_files,
            request_params=request_params,
            folder_path=folder_url,
            output_path=output_path,
        )

        if ifc_path is None:
            raise ValueError(
                "No buildings found in the specified bounding box. "
                "Please try a different area or check your coordinates."
            )

        self.update_state(state="PROGRESS", meta={"percent": 75})

        # File is already saved in the right place - just generate URLs
        url_http = f"{api_settings.URL_OUTPUT_HTTP}/{filename}"
        url_https = f"{api_settings.URL_OUTPUT_HTTPS}/{filename}"

        self.update_state(
            state="PROGRESS",
            meta={
                "percent": 100,
            },
        )

        return {
            "model": {
                "filename": filename,
                "content_type": "application/x-step",
                "url-http": url_http,
                "url-https": url_https,
            }
        }

    except Exception as e:
        self.update_state(
            state=states.FAILURE,
            meta={
                "exc_type": type(e).__name__,
                "exc_message": str(e),
                "error": f"Error generating city model: {str(e)}",
                "troubleshooting": [
                    "Make sure BIMFabrikHH core package is available",
                    "Check that all dependencies are installed",
                    "Verify data directory structure",
                    "Try a smaller bounding box area",
                ],
            },
        )
        raise Ignore()


@app.task(bind=True)
def execute_generate_dgm_model(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute DGM model generation using the generic terrain app in core.

    Args:
        input_data: Input data containing request parameters.

    Returns:
        Dictionary containing task status and results.
    """
    try:
        # Extract request parameters
        request_params = RequestParams(**input_data)
        bbox = request_params.bbox

        # Convert bbox to dict format for DataFetcher
        bbox_dict = {
            "min_x": bbox.min_x,
            "min_y": bbox.min_y,
            "max_x": bbox.max_x,
            "max_y": bbox.max_y,
        }

        # Fetch tile information using API package
        tif_filenames = DataFetcher.fetch_dgm_tiles(bbox_dict)
        if not tif_filenames:
            raise FileNotFoundError(
                "No terrain data found for the specified bounding box"
            )

        # Check tile limit
        if len(tif_filenames) > 4:
            raise ValueError(
                "Anzahl der Kacheln überschreitet die Grenze von 4 Kacheln. "
                "Bitte wählen Sie einen Umring erneut."
            )

        # DGM URL
        dgm_url = f"{api_settings.DATA_BASE_URL}/{api_settings.DATA_DGM_FOLDER}"

        # Generate output path
        filename = (
            f"DGM_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.request.id}.ifc"
        )
        output_path = OUTPUT_FOLDER / filename

        ifc_path = TerrainGenericApp.from_geotiffs(
            tif_filenames,
            request_params=request_params,
            folder_path=dgm_url,
            output_path=output_path,
        )

        if ifc_path is None:
            raise ValueError("Failed to generate IFC data from terrain")

        # Generate URLs
        url_http = f"{api_settings.URL_OUTPUT_HTTP}/{filename}"
        url_https = f"{api_settings.URL_OUTPUT_HTTPS}/{filename}"

        return {
            "model": {
                "filename": filename,
                "content_type": "application/x-step",
                "url-http": url_http,
                "url-https": url_https,
            }
        }

    except Exception as e:
        # Log the error and re-raise so Celery marks task as failed
        logger.error(f"DGM generation failed: {e}")
        raise
