"""
Service module for generating BIM models.

This module provides Celery tasks for generating different types of BIM models:
- Tree models from cadastral data
- City models from CityGML data
- Digital terrain models (DGM) from GeoTIFF data

Copyright (C) 2025 Freie und Hansestadt Hamburg, Landesbetrieb Geoinformation und Vermessung
BIM-Leitstelle, Ahmed Salem <ahmed.salem@gv.hamburg.de>
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from BIMFabrikHH_core import (
    CityGenericApp,
    CityRustApp,
    RequestParams,
    TerrainGenericApp,
    TerrainRustApp,
    TreesGenericApp,
    TreesRustApp,
)
from BIMFabrikHH_core.apps.trees import (
    DEFAULT_OAF_SCHEMA,
    dataframe_to_records,
    tree_crown_detail_from_containers,
)
from BIMFabrikHH_core.core.data_processing import DataProcessor
from BIMFabrikHH_core.core.georeferencing import (
    bbox_request_params_to_epsg25832,
    extract_elevation_df_from_geotiff,
)
from BIMFabrikHH_core.core.ogc_extractor import (
    extract_level_of_geometry,
    extract_psets_basepoint,
)
from celery import Celery

from src.api.config.settings import api_settings
from src.database import get_celery_config

from ..utils.lod_utils import (
    gml_paths_for_rust,
    local_city_folder,
    lod_folder_url,
    transform_file_names_for_lod,
)
from .http_requests import DataFetcher

# Output folder for generated IFC files
OUTPUT_FOLDER = Path(api_settings.OUTPUT_FOLDER_PATH)

logger = logging.getLogger(__name__)

celery_config = get_celery_config()
app = Celery(
    "hamburg", broker=celery_config.broker_url, backend=celery_config.backend_url
)

# Messages shared by the generic and the Rust variant of a model type.
TILE_LIMIT_MESSAGE = (
    "Anzahl der Kacheln überschreitet die Grenze von 4 Kacheln. "
    "Bitte wählen Sie einen Umring erneut."
)
NO_TREE_DATA_MESSAGE = "No tree data found in the specified bounding box"
NO_TREES_MESSAGE = (
    "No trees found in the specified bounding box. "
    "Please try a different area or check your coordinates."
)
NO_BUILDINGS_MESSAGE = (
    "No buildings found in the specified bounding box. "
    "Please try a different area or check your coordinates."
)
NO_TERRAIN_MESSAGE = "No terrain data found for the specified bounding box"
NO_ELEVATION_MESSAGE = (
    "No terrain data found for the specified bounding box - "
    "proceeding without elevation data"
)


def bbox_to_dict(request_params: RequestParams) -> Dict[str, float]:
    """Bounding box in the dict shape DataFetcher expects."""
    bbox = request_params.bbox
    return {
        "min_x": bbox.min_x,
        "min_y": bbox.min_y,
        "max_x": bbox.max_x,
        "max_y": bbox.max_y,
    }


def ifc_result(filename: str) -> Dict[str, Any]:
    """OGC result payload with the download URLs of a written IFC file."""
    return {
        "model": {
            "filename": filename,
            "content_type": "application/x-step",
            "url-http": f"{api_settings.URL_OUTPUT_HTTP}/{filename}",
            "url-https": f"{api_settings.URL_OUTPUT_HTTPS}/{filename}",
        }
    }


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

    try:
        request_params = RequestParams(**input_data)

        self.update_state(state="PROGRESS", meta={"percent": 25})
        bbox_dict = bbox_to_dict(request_params)

        # Fetch raw tree data using API package
        self.update_state(state="PROGRESS", meta={"percent": 50})
        raw_tree_data = DataFetcher.fetch_tree_data(bbox_dict)

        if not raw_tree_data or "features" not in raw_tree_data:
            raise ValueError(NO_TREE_DATA_MESSAGE)

        logger.info(
            "Found %d trees in the bounding box",
            len(raw_tree_data.get("features", [])),
        )

        # Process data using core package
        self.update_state(state="PROGRESS", meta={"percent": 75})

        tif_path = None
        if request_params.use_dgm_elevation:
            tif_filenames = DataFetcher.fetch_dgm_tiles(bbox_dict)
            if not tif_filenames:
                logger.warning(NO_ELEVATION_MESSAGE)
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
            raise ValueError(NO_TREES_MESSAGE)

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
            raise ValueError(NO_TREES_MESSAGE)

        basepoint_psets = extract_psets_basepoint(request_params.containers or [])
        TreesGenericApp.build_ifc(
            records,
            output_path=output_path,
            bbox_wgs84=request_params.bbox_as_wgs84_tuple,
            basepoint_psets=basepoint_psets if basepoint_psets else None,
        )

        self.update_state(state="PROGRESS", meta={"percent": 100})

        # File is already saved in the right place - just generate URLs
        return ifc_result(filename)

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
def execute_generate_tree_model_rs(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Same fetch/records as generate-tree-model; IFC via TreesRustApp."""
    self.update_state(state="PROGRESS", meta={"percent": 0})
    try:
        request_params = RequestParams(**input_data)

        self.update_state(state="PROGRESS", meta={"percent": 25})
        bbox_dict = bbox_to_dict(request_params)

        self.update_state(state="PROGRESS", meta={"percent": 50})
        raw_tree_data = DataFetcher.fetch_tree_data(bbox_dict)
        if not raw_tree_data or "features" not in raw_tree_data:
            raise ValueError(NO_TREE_DATA_MESSAGE)

        tif_path = None
        if request_params.use_dgm_elevation:
            tif_filenames = DataFetcher.fetch_dgm_tiles(bbox_dict)
            if tif_filenames:
                dgm_url = f"{api_settings.DATA_BASE_URL}/{api_settings.DATA_DGM_FOLDER}"
                tif_path = f"{dgm_url}/{tif_filenames[0]}"
            else:
                logger.warning(NO_ELEVATION_MESSAGE)
        else:
            logger.info("Skipping DGM elevation enrichment (use_dgm_elevation=false)")

        filename = (
            f"Baeume_rs_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.request.id}.ifc"
        )
        output_path = OUTPUT_FOLDER / filename

        df = DataProcessor.raw_data_to_dataframe(raw_tree_data)
        if df.empty:
            raise ValueError(NO_TREES_MESSAGE)

        schema = DEFAULT_OAF_SCHEMA
        if tif_path:
            try:
                df = extract_elevation_df_from_geotiff(
                    df, tif_path, schema.easting, schema.northing, schema.elevation
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
            raise ValueError(NO_TREES_MESSAGE)

        self.update_state(state="PROGRESS", meta={"percent": 75})
        bbox_utm = bbox_request_params_to_epsg25832(request_params)
        basepoint = (bbox_utm[0], bbox_utm[1]) if bbox_utm else None
        written = TreesRustApp.build_ifc(
            records, output_path=output_path, basepoint_origin=basepoint
        )
        if written is None:
            raise ValueError("Failed to generate IFC data from trees")

        self.update_state(state="PROGRESS", meta={"percent": 100})
        return ifc_result(filename)

    except Exception as e:
        self.update_state(
            state="FAILURE",
            meta={
                "error": f"Error generating tree model (rs): {str(e)}",
                "troubleshooting": [
                    "Make sure bimfabrikhh-core-rs is installed in the worker environment",
                    "Check that BIMFabrikHH_core is available",
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
        ValueError: If too many tiles are requested, or LoD3 is requested.
        Exception: If model generation fails.
    """
    self.update_state(state="PROGRESS", meta={"percent": 0})

    try:
        request_params = RequestParams(**input_data)

        self.update_state(state="PROGRESS", meta={"percent": 25})
        bbox_dict = bbox_to_dict(request_params)

        # Fetch tile information using API package
        gml_files = DataFetcher.fetch_citymodel_tiles(bbox_dict)
        if len(gml_files) > 4:
            raise ValueError(TILE_LIMIT_MESSAGE)

        # Debug: log ALL containers being sent
        containers = request_params.containers or []
        logger.info(f"Received {len(containers)} containers:")
        for container in containers:
            logger.info(f"  - Container: {container.containerId}")

        # Extract LoD from container components using existing core method
        lod_level = extract_level_of_geometry(request_params.containers)
        logger.info(f"Extracted LoD level: {lod_level}")
        if lod_level == 3:
            raise ValueError(
                "LoD3 is only available on generate-city-model-rs."
            )

        folder_url = lod_folder_url(lod_level)
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
            raise ValueError(NO_BUILDINGS_MESSAGE)

        self.update_state(state="PROGRESS", meta={"percent": 75})
        self.update_state(state="PROGRESS", meta={"percent": 100})

        # File is already saved in the right place - just generate URLs
        return ifc_result(filename)

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
def execute_generate_city_model_rs(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Same tile fetch as generate-city-model; IFC via CityRustApp (mesh)."""
    self.update_state(state="PROGRESS", meta={"percent": 0})
    try:
        request_params = RequestParams(**input_data)

        self.update_state(state="PROGRESS", meta={"percent": 25})
        bbox_dict = bbox_to_dict(request_params)

        gml_files = DataFetcher.fetch_citymodel_tiles(bbox_dict)
        if len(gml_files) > 4:
            raise ValueError(TILE_LIMIT_MESSAGE)

        lod_level = extract_level_of_geometry(request_params.containers)
        folder_url = lod_folder_url(lod_level)
        logger.info(f"Using LoD{lod_level} directory: {folder_url}")

        self.update_state(state="PROGRESS", meta={"percent": 50})
        transformed_gml_files = transform_file_names_for_lod(gml_files, lod_level)
        logger.info(f"Using CityGML tiles: {transformed_gml_files}")

        filename = (
            f"Stadtmodell_rs_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.request.id}.ifc"
        )
        output_path = OUTPUT_FOLDER / filename

        gml_paths = gml_paths_for_rust(
            transformed_gml_files, local_city_folder(folder_url)
        )
        ifc_path = CityRustApp.from_gml_files(
            gml_paths,
            request_params=request_params,
            mode="mesh",
            output_path=output_path,
        )
        if ifc_path is None:
            raise ValueError(NO_BUILDINGS_MESSAGE)

        self.update_state(state="PROGRESS", meta={"percent": 100})
        return ifc_result(filename)

    except Exception as e:
        self.update_state(
            state="FAILURE",
            meta={
                "error": f"Error generating city model (rs): {str(e)}",
                "troubleshooting": [
                    "Make sure bimfabrikhh-core-rs is installed in the worker environment",
                    "Try a smaller bounding box area",
                ],
            },
        )
        raise


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
        bbox_dict = bbox_to_dict(request_params)

        # Fetch tile information using API package
        tif_filenames = DataFetcher.fetch_dgm_tiles(bbox_dict)
        if not tif_filenames:
            raise FileNotFoundError(NO_TERRAIN_MESSAGE)

        # Check tile limit
        if len(tif_filenames) > 4:
            raise ValueError(TILE_LIMIT_MESSAGE)

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

        return ifc_result(filename)

    except Exception as e:
        # Log the error and re-raise so Celery marks task as failed
        logger.error(f"DGM generation failed: {e}")
        raise


@app.task(bind=True)
def execute_generate_dgm_model_rs(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Same GeoTIFF fetch as generate-dgm-model; mesh in Python, IFC via TerrainRustApp."""
    try:
        request_params = RequestParams(**input_data)
        bbox_dict = bbox_to_dict(request_params)

        tif_filenames = DataFetcher.fetch_dgm_tiles(bbox_dict)
        if not tif_filenames:
            raise FileNotFoundError(NO_TERRAIN_MESSAGE)
        if len(tif_filenames) > 4:
            raise ValueError(TILE_LIMIT_MESSAGE)

        dgm_url = f"{api_settings.DATA_BASE_URL}/{api_settings.DATA_DGM_FOLDER}"

        filename = (
            f"DGM_rs_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.request.id}.ifc"
        )
        output_path = OUTPUT_FOLDER / filename

        ifc_path = TerrainRustApp.from_geotiffs(
            tif_filenames,
            request_params=request_params,
            folder_path=dgm_url,
            output_path=output_path,
        )
        if ifc_path is None:
            raise ValueError("Failed to generate IFC data from terrain")

        return ifc_result(filename)

    except Exception as e:
        logger.error(f"DGM generation (rs) failed: {e}")
        raise
