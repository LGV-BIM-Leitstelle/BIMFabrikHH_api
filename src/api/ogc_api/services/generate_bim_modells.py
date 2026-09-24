"""
Service module for generating BIM models.

This module provides Celery tasks for generating different types of BIM models:
- Tree models from cadastral data
- City models from CityGML data
- Digital terrain models (DGM) from GeoTIFF data
- Flurstueck (cadastral parcel) models from ALKIS OAF data
- Borehole (Baugrundaufschluss) models from BoreholeML 3.0 WFS data

Copyright (C) 2025 Freie und Hansestadt Hamburg, Landesbetrieb Geoinformation und Vermessung
BIM-Leitstelle, Ahmed Salem <ahmed.salem@gv.hamburg.de>, Polichronis Muratidis <polichronis.muratidis@gv.hamburg.de>
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from BIMFabrikHH_core.apps.city.generic.app import CityGenericApp
from BIMFabrikHH_core.apps.city.generic_rust import CityRustApp
from BIMFabrikHH_core.apps.flurstuecke.generic.app import FlurstueckeGenericApp
from BIMFabrikHH_core.apps.terrain.generic.app import TerrainGenericApp
from BIMFabrikHH_core.apps.terrain.generic_rust import TerrainRustApp
from BIMFabrikHH_core.apps.trees.column_schema import DEFAULT_OAF_SCHEMA
from BIMFabrikHH_core.apps.trees.generic.app import TreesGenericApp
from BIMFabrikHH_core.apps.trees.generic_rust import TreesRustApp
from BIMFabrikHH_core.apps.trees.processing import (
    dataframe_to_records,
    tree_crown_detail_from_containers,
    tree_log_from_containers,
)
from BIMFabrikHH_core.config.paths import local_dir_or_raw
from BIMFabrikHH_core.core.data_processing import DataProcessor
from BIMFabrikHH_core.core.georeferencing import bbox_request_params_to_epsg25832
from BIMFabrikHH_core.core.ogc_extractor import (
    extract_level_of_geometry,
    extract_psets_basepoint,
)
from BIMFabrikHH_core.data_models.flurstuecke import (
    records_from_geojson_feature_collection as flurstuecke_records_from_geojson,
)
from BIMFabrikHH_core.data_models.params_tree import RequestParams
from celery import Celery
from celery.signals import setup_logging as celery_setup_logging
from celery.signals import task_failure, task_postrun, task_revoked

from src.api.config.logging_config import setup_logging as configure_logging
from src.api.config.settings import api_settings
from src.database import get_celery_config

from ..utils.lod_utils import (
    gml_paths_for_rust,
    lod_folder_url,
    transform_file_names_for_lod,
)
from ..utils.umring_limits import (
    ensure_bbox_area,
    ensure_borehole_bbox_area,
    ensure_tile_count,
)
from ..utils.user_messages import (
    BOREHOLES_IFC_FAILED_MESSAGE,
    CORE_BOREHOLES_MISSING_MESSAGE,
    FLURSTUECKE_IFC_FAILED_MESSAGE,
    LOD3_ONLY_ON_RS_MESSAGE,
    NO_BOREHOLE_DATA_MESSAGE,
    NO_BOREHOLES_MESSAGE,
    NO_BUILDINGS_MESSAGE,
    NO_FLURSTUECK_DATA_MESSAGE,
    NO_FLURSTUECKE_MESSAGE,
    NO_TERRAIN_MESSAGE,
    NO_TREE_DATA_MESSAGE,
    NO_TREES_MESSAGE,
    TERRAIN_IFC_FAILED_MESSAGE,
    TREES_IFC_FAILED_MESSAGE,
    to_user_error,
)
from .http_requests import DataFetcher, HamburgOGCAPI

try:
    from BIMFabrikHH_core.apps.boreholes import BoreholeMLProcessor, BoreholesGenericApp
except ImportError:  # core feat/boreholes is not on main yet
    BoreholesGenericApp = None
    BoreholeMLProcessor = None

# Output folder for generated IFC files
OUTPUT_FOLDER = Path(api_settings.OUTPUT_FOLDER_PATH)

logger = logging.getLogger(__name__)


@celery_setup_logging.connect
def _configure_worker_logging(**_kwargs: Any) -> None:
    """Apply the shared logging configuration inside the Celery worker.

    Connecting a receiver to Celery's ``setup_logging`` signal disables Celery's
    own logging setup, so the worker (and its prefork child processes) uses the
    same console and shared rotating file handlers as the API process.
    """
    configure_logging(force=True)


celery_config = get_celery_config()
app = Celery(
    "hamburg", broker=celery_config.broker_url, backend=celery_config.backend_url
)

# Task queue, routing and reliability configuration.
#
# All model-generation tasks are CPU-heavy and equivalent in weight, so they
# share a single dedicated "processing" queue instead of per-model-type queues.
# ``task_routes`` maps every task in this module to that queue, and
# ``task_default_queue`` makes it the default so the worker only needs
# ``-Q processing``.
#
# ``worker_prefetch_multiplier=1`` makes a worker reserve only one task at a
# time, so long jobs are load-balanced evenly instead of one child hoarding the
# backlog. ``task_acks_late=True`` acknowledges a task only after it completes,
# so an in-flight job survives a worker crash (it is redelivered).
# ``task_track_started=True`` writes STARTED to the result backend so
# GET /ogc/jobs/{id} can show OGC ``running`` instead of staying ``accepted``.
#
# ``worker_redirect_stdouts=False`` stops Celery from replacing ``sys.stdout``/
# ``sys.stderr`` with a logging proxy. Logging is configured explicitly via the
# ``setup_logging`` signal, so leaving the redirect on would route stray stdout
# writes back through the logging system and risk duplicate console lines.
#
# ``task_send_sent_event=True`` makes the API process (the Celery *client*)
# emit a ``task-sent`` event as soon as a job is queued, instead of only once a
# worker picks it up. Without it, a job stuck behind a busy worker is invisible
# in monitoring tools such as Flower until it starts running.
PROCESSING_QUEUE = "processing"
app.conf.update(
    task_default_queue=PROCESSING_QUEUE,
    task_routes={f"{__name__}.*": {"queue": PROCESSING_QUEUE}},
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_track_started=True,
    worker_redirect_stdouts=False,
    task_time_limit=api_settings.CELERY_TASK_TIME_LIMIT,
    task_send_sent_event=True,
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


@task_failure.connect
def _on_task_failure(task_id: str = None, **kwargs: Any) -> None:
    """Release the concurrency slot on task failure, including hard timeouts.

    A hard Celery time limit SIGKILLs the worker child process, so the task
    never returns normally and ``task_postrun`` never fires for it; only
    ``task_failure`` is emitted (from the parent worker process). Without this
    handler, a hard-timeout kill would permanently leak the admission-control
    concurrency slot.
    """
    _release_admission_slot(task_id)


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


def empty_result(message: str) -> Dict[str, Any]:
    """Successful job with no IFC — the umring simply had no features."""
    return {"message": message, "model": None}


def dgm_folder() -> str:
    """DGM tile directory, as a path this OS can open."""
    return local_dir_or_raw(
        f"{api_settings.DATA_BASE_URL}/{api_settings.DATA_DGM_FOLDER}"
    )


def tree_dgm_tiles(
    request_params: RequestParams, bbox_dict: Dict[str, float]
) -> Tuple[Optional[List[str]], Optional[str]]:
    """DGM tiles + folder for the tree Z drape, or ``(None, None)``.

    On by default (``RequestParams.use_dgm_elevation``); the umring may still
    touch no tile. Pass ``use_dgm_elevation=false`` to skip.
    """
    if not request_params.use_dgm_elevation:
        logger.info("Skipping DGM elevation enrichment (use_dgm_elevation=false)")
        return None, None
    tif_files = DataFetcher.fetch_dgm_tiles(bbox_dict)
    if not tif_files:
        logger.warning(NO_ELEVATION_MESSAGE)
        return None, None
    logger.info("Using %d DGM GeoTIFF tile(s) for tree Z", len(tif_files))
    return tif_files, dgm_folder()


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

    logger.info("Input data for tree model generation: %s", input_data)
    try:
        request_params = RequestParams(**input_data)
        ensure_bbox_area(request_params)

        self.update_state(state="PROGRESS", meta={"percent": 25})
        bbox_dict = bbox_to_dict(request_params)

        # Fetch raw tree data using API package
        self.update_state(state="PROGRESS", meta={"percent": 50})
        raw_tree_data = DataFetcher.fetch_tree_data(bbox_dict)

        if not raw_tree_data or "features" not in raw_tree_data:
            raise ValueError(NO_TREE_DATA_MESSAGE)

        tree_count = len(raw_tree_data.get("features", []))
        logger.info("Found %s trees in the bounding box", tree_count)

        # Process data using core package
        self.update_state(state="PROGRESS", meta={"percent": 75})

        tif_files, folder = tree_dgm_tiles(request_params, bbox_dict)

        # Generate output path for API's output folder
        filename = (
            f"Baeume_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.request.id}.ifc"
        )
        output_path = OUTPUT_FOLDER / filename

        df = DataProcessor.raw_data_to_dataframe(raw_tree_data)
        if df.empty:
            logger.info(NO_TREES_MESSAGE)
            return empty_result(NO_TREES_MESSAGE)

        schema = DEFAULT_OAF_SCHEMA
        records = dataframe_to_records(
            df,
            aufnahmedatum=datetime.now().strftime("%Y-%m-%d"),
            schema=schema,
            source_name="BIMFabrikHH_api",
            detail=tree_crown_detail_from_containers(request_params.containers),
            log=tree_log_from_containers(request_params.containers),
        )
        if not records:
            logger.info(NO_TREES_MESSAGE)
            return empty_result(NO_TREES_MESSAGE)

        basepoint_psets = extract_psets_basepoint(request_params.containers or [])
        TreesGenericApp.build_ifc(
            records,
            output_path=output_path,
            bbox_wgs84=request_params.bbox_as_wgs84_tuple,
            basepoint_psets=basepoint_psets if basepoint_psets else None,
            tif_files=tif_files,
            dgm_folder=folder,
        )

        self.update_state(state="PROGRESS", meta={"percent": 100})

        logger.info(
            "Tree model generated successfully: %s (task %s)", filename, self.request.id
        )
        return ifc_result(filename)

    except Exception as e:
        logger.exception(
            "Tree model generation failed (task %s): %s", self.request.id, e
        )
        raise to_user_error(e) from e


@app.task(bind=True)
def execute_generate_tree_model_rs(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Same fetch/records as generate-tree-model; IFC via TreesRustApp."""
    self.update_state(state="PROGRESS", meta={"percent": 0})
    try:
        request_params = RequestParams(**input_data)
        ensure_bbox_area(request_params)

        self.update_state(state="PROGRESS", meta={"percent": 25})
        bbox_dict = bbox_to_dict(request_params)

        self.update_state(state="PROGRESS", meta={"percent": 50})
        raw_tree_data = DataFetcher.fetch_tree_data(bbox_dict)
        if not raw_tree_data or "features" not in raw_tree_data:
            raise ValueError(NO_TREE_DATA_MESSAGE)

        tif_files, folder = tree_dgm_tiles(request_params, bbox_dict)

        filename = f"Baeume_rs_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.request.id}.ifc"
        output_path = OUTPUT_FOLDER / filename

        df = DataProcessor.raw_data_to_dataframe(raw_tree_data)
        if df.empty:
            logger.info(NO_TREES_MESSAGE)
            return empty_result(NO_TREES_MESSAGE)

        schema = DEFAULT_OAF_SCHEMA
        records = dataframe_to_records(
            df,
            aufnahmedatum=datetime.now().strftime("%Y-%m-%d"),
            schema=schema,
            source_name="BIMFabrikHH_api",
            detail=tree_crown_detail_from_containers(request_params.containers),
            log=tree_log_from_containers(request_params.containers),
        )
        if not records:
            logger.info(NO_TREES_MESSAGE)
            return empty_result(NO_TREES_MESSAGE)

        self.update_state(state="PROGRESS", meta={"percent": 75})
        bbox_utm = bbox_request_params_to_epsg25832(request_params)
        basepoint = (bbox_utm[0], bbox_utm[1]) if bbox_utm else None
        written = TreesRustApp.build_ifc(
            records,
            output_path=output_path,
            basepoint_origin=basepoint,
            tif_files=tif_files,
            dgm_folder=folder,
        )
        if written is None:
            raise ValueError(TREES_IFC_FAILED_MESSAGE)

        self.update_state(state="PROGRESS", meta={"percent": 100})
        return ifc_result(filename)

    except Exception as e:
        logger.exception(
            "Tree model generation (rs) failed (task %s): %s", self.request.id, e
        )
        raise to_user_error(e) from e


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

    logger.info("Starting city model generation (task %s)", self.request.id)
    try:
        request_params = RequestParams(**input_data)
        ensure_bbox_area(request_params)

        self.update_state(state="PROGRESS", meta={"percent": 25})
        bbox_dict = bbox_to_dict(request_params)

        # Fetch tile information using API package
        gml_files = DataFetcher.fetch_citymodel_tiles(bbox_dict)
        ensure_tile_count(len(gml_files))

        # Debug: log ALL containers being sent
        containers = request_params.containers or []
        logger.info(f"Received {len(containers)} containers:")
        for container in containers:
            logger.info(f"  - Container: {container.containerId}")

        # Extract LoD from container components using existing core method
        lod_level = extract_level_of_geometry(request_params.containers)
        logger.info(f"Extracted LoD level: {lod_level}")
        if lod_level == 3:
            raise ValueError(LOD3_ONLY_ON_RS_MESSAGE)

        # Resolve the folder once: the tile extension is picked by probing the
        # directory, so that probe and the read below must use the same,
        # OS-openable form. Hamburg ships LoD1 as .xml but LoD2 as .gml.
        local_folder = local_dir_or_raw(lod_folder_url(lod_level))
        logger.info(f"Using LoD{lod_level} directory: {local_folder}")

        self.update_state(state="PROGRESS", meta={"percent": 50})

        # Transform file names if needed
        transformed_gml_files = transform_file_names_for_lod(
            gml_files, lod_level, local_folder
        )
        logger.info(f"Using CityGML tiles: {transformed_gml_files}")

        # Generate output path for API's output folder
        filename = f"Stadtmodell_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.request.id}.ifc"
        output_path = OUTPUT_FOLDER / filename

        ifc_path = CityGenericApp.from_gml_files(
            transformed_gml_files,
            request_params=request_params,
            folder_path=local_folder,
            output_path=output_path,
        )
        if ifc_path is None:
            logger.info(NO_BUILDINGS_MESSAGE)
            return empty_result(NO_BUILDINGS_MESSAGE)

        self.update_state(state="PROGRESS", meta={"percent": 75})
        self.update_state(state="PROGRESS", meta={"percent": 100})

        logger.info(
            "City model generated successfully: %s (task %s)", filename, self.request.id
        )
        return ifc_result(filename)

    except Exception as e:
        logger.exception(
            "City model generation failed (task %s): %s", self.request.id, e
        )
        raise to_user_error(e) from e


@app.task(bind=True)
def execute_generate_city_model_rs(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Same tile fetch as generate-city-model; IFC via CityRustApp (mesh)."""
    self.update_state(state="PROGRESS", meta={"percent": 0})
    try:
        request_params = RequestParams(**input_data)
        ensure_bbox_area(request_params)

        self.update_state(state="PROGRESS", meta={"percent": 25})
        bbox_dict = bbox_to_dict(request_params)

        gml_files = DataFetcher.fetch_citymodel_tiles(bbox_dict)
        ensure_tile_count(len(gml_files))

        lod_level = extract_level_of_geometry(request_params.containers)
        # Resolve the folder once: the tile extension is picked by probing the
        # directory, so that probe and the final paths must use the same,
        # OS-openable form. Hamburg ships LoD1 as .xml but LoD2 as .gml.
        local_folder = local_dir_or_raw(lod_folder_url(lod_level))
        logger.info(f"Using LoD{lod_level} directory: {local_folder}")

        self.update_state(state="PROGRESS", meta={"percent": 50})
        transformed_gml_files = transform_file_names_for_lod(
            gml_files, lod_level, local_folder
        )
        logger.info(f"Using CityGML tiles: {transformed_gml_files}")

        filename = f"Stadtmodell_rs_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.request.id}.ifc"
        output_path = OUTPUT_FOLDER / filename

        gml_paths = gml_paths_for_rust(transformed_gml_files, local_folder)
        ifc_path = CityRustApp.from_gml_files(
            gml_paths,
            request_params=request_params,
            mode="mesh",
            output_path=output_path,
        )
        if ifc_path is None:
            logger.info(NO_BUILDINGS_MESSAGE)
            return empty_result(NO_BUILDINGS_MESSAGE)

        self.update_state(state="PROGRESS", meta={"percent": 100})
        return ifc_result(filename)

    except Exception as e:
        logger.exception(
            "City model generation (rs) failed (task %s): %s", self.request.id, e
        )
        raise to_user_error(e) from e


@app.task(bind=True)
def execute_generate_dgm_model(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute DGM model generation using the generic terrain app in core.

    Args:
        input_data: Input data containing request parameters.

    Returns:
        Dictionary containing task status and results.
    """
    logger.info("Starting DGM model generation (task %s)", self.request.id)
    try:
        # Extract request parameters
        request_params = RequestParams(**input_data)
        ensure_bbox_area(request_params)
        bbox_dict = bbox_to_dict(request_params)

        # Fetch tile information using API package
        tif_filenames = DataFetcher.fetch_dgm_tiles(bbox_dict)
        if not tif_filenames:
            logger.info(NO_TERRAIN_MESSAGE)
            return empty_result(NO_TERRAIN_MESSAGE)

        ensure_tile_count(len(tif_filenames))

        # Generate output path
        filename = (
            f"DGM_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.request.id}.ifc"
        )
        output_path = OUTPUT_FOLDER / filename

        lod_level = extract_level_of_geometry(request_params.containers)
        logger.info("Extracted DGM type (level_of_geom): %s", lod_level)

        ifc_path = TerrainGenericApp.from_geotiffs(
            tif_filenames,
            request_params=request_params,
            folder_path=dgm_folder(),
            output_path=output_path,
            guide_from_oaf=lod_level == 2,
        )
        if ifc_path is None:
            raise ValueError(TERRAIN_IFC_FAILED_MESSAGE)

        logger.info(
            "DGM model generated successfully: %s (task %s)", filename, self.request.id
        )
        return ifc_result(filename)

    except Exception as e:
        # Log the error and re-raise so Celery marks task as failed
        logger.exception("DGM generation failed (task %s): %s", self.request.id, e)
        raise to_user_error(e) from e


@app.task(bind=True)
def execute_generate_dgm_model_rs(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Same GeoTIFF fetch as generate-dgm-model; mesh in Python, IFC via TerrainRustApp."""
    try:
        request_params = RequestParams(**input_data)
        ensure_bbox_area(request_params)
        bbox_dict = bbox_to_dict(request_params)

        tif_filenames = DataFetcher.fetch_dgm_tiles(bbox_dict)
        if not tif_filenames:
            logger.info(NO_TERRAIN_MESSAGE)
            return empty_result(NO_TERRAIN_MESSAGE)
        ensure_tile_count(len(tif_filenames))

        filename = (
            f"DGM_rs_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.request.id}.ifc"
        )
        output_path = OUTPUT_FOLDER / filename

        lod_level = extract_level_of_geometry(request_params.containers)
        logger.info("Extracted DGM type (level_of_geom): %s", lod_level)

        ifc_path = TerrainRustApp.from_geotiffs(
            tif_filenames,
            request_params=request_params,
            folder_path=dgm_folder(),
            output_path=output_path,
            guide_from_oaf=lod_level == 2,
        )
        if ifc_path is None:
            raise ValueError(TERRAIN_IFC_FAILED_MESSAGE)

        return ifc_result(filename)

    except Exception as e:
        logger.exception(
            "DGM model generation (rs) failed (task %s): %s", self.request.id, e
        )
        raise to_user_error(e) from e


@app.task(bind=True)
def execute_generate_flurstuecke_model(
    self, input_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate a BIM model of ALKIS Flurstuecke (cadastral parcels) from OAF data.

    Args:
        self: Celery task instance.
        input_data: Dictionary containing request parameters including bounding box.

    Returns:
        Dict containing model information including download URLs.

    Raises:
        Exception: If model generation fails.
    """
    self.update_state(state="PROGRESS", meta={"percent": 0})

    logger.info("Starting Flurstuecke model generation (task %s)", self.request.id)
    try:
        request_params = RequestParams(**input_data)
        ensure_bbox_area(request_params)

        self.update_state(state="PROGRESS", meta={"percent": 25})
        bbox_dict = bbox_to_dict(request_params)

        self.update_state(state="PROGRESS", meta={"percent": 50})
        raw_flurstueck_data = HamburgOGCAPI.fetch_all_features(
            str(api_settings.FLURSTUECKE_API_URL),
            {
                "f": "json",
                "bbox": (
                    f"{bbox_dict['min_x']},{bbox_dict['min_y']},"
                    f"{bbox_dict['max_x']},{bbox_dict['max_y']}"
                ),
                "crs": HamburgOGCAPI.DEFAULT_CRS,
                "limit": HamburgOGCAPI.DEFAULT_LIMIT,
                "skipGeometry": "false",
            },
        )
        if not raw_flurstueck_data or "features" not in raw_flurstueck_data:
            raise ValueError(NO_FLURSTUECK_DATA_MESSAGE)

        # The fetch asks for EPSG:25832 geometries, which is the CRS the app
        # extrudes the parcel footprints in.
        records = flurstuecke_records_from_geojson(
            raw_flurstueck_data, geometry_crs="EPSG:25832"
        )
        if not records:
            logger.info(NO_FLURSTUECKE_MESSAGE)
            return empty_result(NO_FLURSTUECKE_MESSAGE)
        logger.info("Found %s Flurstuecke in the bounding box", len(records))

        self.update_state(state="PROGRESS", meta={"percent": 75})
        filename = f"Flurstuecke_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.request.id}.ifc"
        output_path = OUTPUT_FOLDER / filename

        ifc_path = FlurstueckeGenericApp.build_ifc(
            records,
            request_params=request_params,
            output_path=output_path,
        )
        if ifc_path is None:
            raise ValueError(FLURSTUECKE_IFC_FAILED_MESSAGE)

        self.update_state(state="PROGRESS", meta={"percent": 100})

        logger.info(
            "Flurstuecke model generated successfully: %s (task %s)",
            filename,
            self.request.id,
        )
        return ifc_result(filename)

    except Exception as e:
        logger.exception(
            "Flurstuecke model generation failed (task %s): %s", self.request.id, e
        )
        raise to_user_error(e) from e


@app.task(bind=True)
def execute_generate_boreholes_model(
    self, input_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate a BIM model of Baugrundaufschluesse from BoreholeML 3.0 WFS data.

    Args:
        self: Celery task instance.
        input_data: Dictionary containing request parameters including bounding box.

    Returns:
        Dict containing model information including download URLs.

    Raises:
        Exception: If model generation fails.
    """
    self.update_state(state="PROGRESS", meta={"percent": 0})

    logger.info("Starting borehole model generation (task %s)", self.request.id)
    try:
        request_params = RequestParams(**input_data)
        ensure_borehole_bbox_area(request_params)

        self.update_state(state="PROGRESS", meta={"percent": 25})
        bbox_dict = bbox_to_dict(request_params)

        self.update_state(state="PROGRESS", meta={"percent": 50})
        xml_root = DataFetcher.fetch_borehole_data(bbox_dict)
        if xml_root is None:
            raise ValueError(NO_BOREHOLE_DATA_MESSAGE)
        if BoreholeMLProcessor is None:
            raise ImportError(CORE_BOREHOLES_MISSING_MESSAGE)

        processor = BoreholeMLProcessor()
        records = processor.parse(xml_root)
        if not records:
            logger.info(NO_BOREHOLES_MESSAGE)
            return empty_result(NO_BOREHOLES_MESSAGE)
        logger.info("Found %s boreholes in the bounding box", len(records))

        self.update_state(state="PROGRESS", meta={"percent": 75})
        if BoreholesGenericApp is None:
            raise ImportError(CORE_BOREHOLES_MISSING_MESSAGE)
        filename = (
            f"Baugrundaufschluesse_{datetime.now().strftime('%Y%m%d_%H%M%S')}_"
            f"{self.request.id}.ifc"
        )
        output_path = OUTPUT_FOLDER / filename

        ifc_path = BoreholesGenericApp.build_ifc(
            records,
            request_params=request_params,
            output_path=output_path,
        )
        if ifc_path is None:
            raise ValueError(BOREHOLES_IFC_FAILED_MESSAGE)

        self.update_state(state="PROGRESS", meta={"percent": 100})

        logger.info(
            "Borehole model generated successfully: %s (task %s)",
            filename,
            self.request.id,
        )
        return ifc_result(filename)

    except Exception as e:
        logger.exception(
            "Borehole model generation failed (task %s): %s", self.request.id, e
        )
        raise to_user_error(e) from e
