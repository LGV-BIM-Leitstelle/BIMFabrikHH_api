"""
OAF (OpenAPI Features) endpoints for BIMFabrikHH API.

This module provides endpoints for accessing OpenAPI Features data
from Hamburg's geospatial services including trees, city models, and DGM tiles.

Copyright (C) 2025 Freie und Hansestadt Hamburg, Landesbetrieb Geoinformation und Vermessung
BIM-Leitstelle, Ahmed Salem <ahmed.salem@gv.hamburg.de>
"""

import logging
from typing import List

from BIMFabrikHH_core.data_models.params_bbox import BoundingBoxParams
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import JSONResponse

from ..ogc_api.services.http_requests import DataFetcher

router = APIRouter()

LOGGER = logging.getLogger(__name__)


@router.get(
    "/bimfabrikhh-datasets/oaf-trees",
    response_class=Response,
    tags=["Strassenbaumkataster Hamburg"],
    description="Get trees from OGC API Features Hamburg",
)
def get_oaf_trees(bbox: BoundingBoxParams = Depends()) -> JSONResponse:
    """
    Retrieve tree data from Hamburg's OGC API Features service.

    Args:
        bbox: Bounding box parameters defining the area of interest.

    Returns:
        JSONResponse: Tree data within the specified bounding box.

    Raises:
        HTTPException: If there's an error fetching tree data.
    """
    try:
        # Convert bbox to dict format for DataFetcher
        bbox_dict = {
            "min_x": bbox.min_x,
            "min_y": bbox.min_y,
            "max_x": bbox.max_x,
            "max_y": bbox.max_y,
        }

        # Fetch raw tree data using API package
        trees_data: dict = DataFetcher.fetch_tree_data(bbox_dict)

        return JSONResponse(content=trees_data)
    except Exception as e:
        LOGGER.error("An error occurred: %s" % e)
        raise HTTPException(
            status_code=500, detail=f"Error fetching tree data: {str(e)}"
        )


@router.get(
    "/bimfabrikhh-datasets/oaf-trees-hafen",
    response_class=Response,
    tags=["Strassenbaumkataster Hamburg Hafen"],
    description="Get harbor trees from OGC API Features Hamburg",
)
def get_oaf_trees_hafen(bbox: BoundingBoxParams = Depends()) -> JSONResponse:
    """
    Retrieve harbor tree data from Hamburg's OGC API Features service.

    Args:
        bbox: Bounding box parameters defining the area of interest.

    Returns:
        JSONResponse: Harbor tree data within the specified bounding box.

    Raises:
        HTTPException: If there's an error fetching harbor tree data.
    """
    try:
        # Convert bbox to dict format for DataFetcher
        bbox_dict = {
            "min_x": bbox.min_x,
            "min_y": bbox.min_y,
            "max_x": bbox.max_x,
            "max_y": bbox.max_y,
        }

        # Fetch raw harbor tree data using API package
        trees_data: dict = DataFetcher.fetch_tree_data_hafen(bbox_dict)

        return JSONResponse(content=trees_data)
    except Exception as e:
        LOGGER.error("An error occurred: %s" % e)
        raise HTTPException(
            status_code=500, detail=f"Error fetching harbor tree data: {str(e)}"
        )


@router.get(
    "/bimfabrikhh-datasets/oaf-citymodell-tiles",
    response_class=Response,
    tags=["Stadtmodell Hamburg"],
    description="Get Tiles-Citymodell from OGC API Features Hamburg",
)
def get_oaf_citymodell(bbox: BoundingBoxParams = Depends()) -> JSONResponse:
    """
    Retrieve city model tile information from Hamburg's OGC API Features service.

    Args:
        bbox: Bounding box parameters defining the area of interest.

    Returns:
        JSONResponse: City model tile data within the specified bounding box.

    Raises:
        HTTPException: If there's an error fetching city model tiles.
    """
    try:
        # Convert bbox to dict format for DataFetcher
        bbox_dict = {
            "min_x": bbox.min_x,
            "min_y": bbox.min_y,
            "max_x": bbox.max_x,
            "max_y": bbox.max_y,
        }

        # Fetch tile information using API package
        citymodel_tiles: List = DataFetcher.fetch_citymodel_tiles(bbox_dict)

        return JSONResponse(content=citymodel_tiles)
    except Exception as e:
        LOGGER.error("An error occurred: %s" % e)
        raise HTTPException(
            status_code=500, detail=f"Error fetching citymodel tiles: {str(e)}"
        )


@router.get(
    "/bimfabrikhh-datasets/get-oaf-basic-tiles",
    response_class=Response,
    tags=["Digitales Höhenmodell Hamburg DGM 1"],
    description="Get Tiles-DGM from OGC API Features Hamburg",
)
def get_oaf_dgm(bbox: BoundingBoxParams = Depends()) -> JSONResponse:
    """
    Retrieve DGM (Digital Terrain Model) tile information from Hamburg's OGC API Features service.

    Args:
        bbox: Bounding box parameters defining the area of interest.

    Returns:
        JSONResponse: DGM tile data within the specified bounding box.

    Raises:
        HTTPException: If there's an error fetching DGM tiles.
    """
    try:
        # Convert bbox to dict format for DataFetcher
        bbox_dict = {
            "min_x": bbox.min_x,
            "min_y": bbox.min_y,
            "max_x": bbox.max_x,
            "max_y": bbox.max_y,
        }

        # Fetch tile information using API package
        dgm_tiles: List = DataFetcher.fetch_dgm_tiles(bbox_dict)

        return JSONResponse(content=dgm_tiles)
    except Exception as e:
        LOGGER.error("An error occurred: %s" % e)
        raise HTTPException(
            status_code=500, detail=f"Error fetching DGM tiles: {str(e)}"
        )
