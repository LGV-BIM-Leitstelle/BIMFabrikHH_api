"""
Service module for generating BIM models.

This module provides Celery tasks for generating different types of BIM models:
- Tree models from cadastral data
- City models from CityGML data
- Digital terrain models (DGM) from GeoTIFF data

Copyright (C) 2025 Freie und Hansestadt Hamburg, Landesbetrieb Geoinformation und Vermessung
BIM-Leitstelle, Ahmed Salem <ahmed.salem@gv.hamburg.de>
"""

from typing import Any, Dict
import logging
from datetime import datetime
from pathlib import Path

from BIMFabrikHH_core.apps.city.app import CityModularApp
from BIMFabrikHH_core.apps.terrain.filtered.app import process_terrain_folder_to_ifc
from BIMFabrikHH_core.apps.trees.basic.app import BaumModeller
from BIMFabrikHH_core.core.ogc_extractor.ogc_values_extractor import (
    extract_level_of_geometry,
)
from BIMFabrikHH_core.data_models.params_tree import RequestParams

from ..utils.lod_utils import transform_file_names_for_lod
from celery import Celery

from src.database import CELERY_BACKEND_URL, CELERY_BROKER_URL
from src.api.config.settings import api_settings
from .http_requests import DataFetcher

# Output folder for generated IFC files
OUTPUT_FOLDER = Path(api_settings.OUTPUT_FOLDER_PATH)

baum_modeller = BaumModeller()
terrain_app = None
logger = logging.getLogger(__name__)

app = Celery("hamburg", broker=CELERY_BROKER_URL, backend=CELERY_BACKEND_URL)


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

        # Fetch specific GeoTIFF files based on coordinates (same as DGM app)
        tif_filenames = DataFetcher.fetch_dgm_tiles(bbox_dict)
        if not tif_filenames:
            logger.warning("No terrain data found for the specified bounding box - proceeding without elevation data")
            tif_path = None
        else:
            # Use URL directly - core library supports in-memory processing from URLs
            dgm_url = f"{api_settings.DATA_BASE_URL}/{api_settings.DATA_DGM_FOLDER}"
            tif_path = f"{dgm_url}/{tif_filenames[0]}"
            logger.info(f"Using GeoTIFF URL for elevation (in-memory processing): {tif_path}")

        # Generate output path for API's output folder
        filename = f"Baeume_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.request.id}.ifc"
        output_path = OUTPUT_FOLDER / filename

        # Create tree model - saves directly to API's output folder
        ifc_path = baum_modeller.create_tree_model(
            raw_tree_data=raw_tree_data, 
            model_params=request_params, 
            tif_path=tif_path,
            output_path=output_path
        )

        if ifc_path is None:
            raise ValueError(
                "No trees found in the specified bounding box. Please try a different area or check your coordinates."
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
            state="FAILURE",
            meta={
                "error": f"Error generating tree model: {str(e)}",
                "troubleshooting": [
                    "Make sure BIMFabrikHH core package is available",
                    "Check that all dependencies are installed",
                    "Verify internet connection for API calls",
                    "Try a different bounding box area",
                ],
            },
        )
        raise


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
        logger.info(f"Received {len(request_params.containers)} containers:")
        for container in request_params.containers:
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

        # Create new city app for each request (tiles vary by bbox)
        city_app = CityModularApp(transformed_gml_files, folder_url)

        # Use modular app to process data
        raw_buildings = city_app.get_data_in_bbox(bbox)
        if not raw_buildings:
            raise ValueError(
                "No buildings found in the specified bounding box. "
                "Please try a different area or check your coordinates."
            )

        processed_buildings = city_app.process_data(raw_buildings)

        # Generate output path for API's output folder
        filename = f"Stadtmodell_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.request.id}.ifc"
        output_path = OUTPUT_FOLDER / filename

        # Create IFC using modular app - saves directly to API's output folder
        ifc_path = city_app.create_ifc(processed_buildings, request_params, output_path=output_path)

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
            state="FAILURE",
            meta={
                "error": f"Error generating city model: {str(e)}",
                "troubleshooting": [
                    "Make sure BIMFabrikHH core package is available",
                    "Check that all dependencies are installed",
                    "Verify data directory structure",
                    "Try a smaller bounding box area",
                ],
            },
        )
        raise


@app.task(bind=True)
def execute_generate_dgm_model(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute DGM model generation using filtered terrain app.

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
            raise FileNotFoundError("No terrain data found for the specified bounding box")

        # Check tile limit
        if len(tif_filenames) > 4:
            raise ValueError(
                "Anzahl der Kacheln überschreitet die Grenze von 4 Kacheln. "
                "Bitte wählen Sie einen Umring erneut."
            )

        # DGM URL
        dgm_url = f"{api_settings.DATA_BASE_URL}/{api_settings.DATA_DGM_FOLDER}"

        # Generate output path
        filename = f"DGM_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.request.id}.ifc"
        output_path = OUTPUT_FOLDER / filename

        # Process terrain data to IFC (saves directly to output_path and returns bytes)
        ifc_bytes = process_terrain_folder_to_ifc(
            folder_path=dgm_url,
            tif_files=tif_filenames,
            input_data=request_params,
            output_path=output_path,
        )

        if ifc_bytes is None:
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
