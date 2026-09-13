"""
OAF (OpenAPI Features) endpoints for BIMFabrikHH API.

This module provides endpoints for accessing OpenAPI Features data
from Hamburg's geospatial services including trees, city models, DGM tiles,
ALKIS Flurstuecke and Baugrundaufschluesse.

Copyright (C) 2025 Freie und Hansestadt Hamburg, Landesbetrieb Geoinformation und Vermessung
BIM-Leitstelle, Ahmed Salem <ahmed.salem@gv.hamburg.de>
"""

import logging
from typing import List

from BIMFabrikHH_core.data_models.params_bbox import BoundingBoxParams
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import JSONResponse

from lxml import etree

from ..config.settings import api_settings
from ..ogc_api.services.http_requests import DataFetcher, HamburgOGCAPI

router = APIRouter()

BMLH_NS = "http://www.infogeo.de/boreholeml/3.0/header"

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
    "/bimfabrikhh-datasets/oaf-flurstuecke",
    response_class=Response,
    tags=["ALKIS Flurstuecke Hamburg"],
    description="Get ALKIS Flurstuecke from OGC API Features Hamburg",
)
def get_oaf_flurstuecke(bbox: BoundingBoxParams = Depends()) -> JSONResponse:
    """
    Count ALKIS Flurstuecke in the umring, plus the Gemarkungen on the first page.

    Geometry is skipped and only one page is fetched: ``numberMatched`` is the
    full count, and the Gemarkung names come from that page's properties.

    Args:
        bbox: Bounding box parameters defining the area of interest.

    Returns:
        JSONResponse: ``count``, sorted unique ``gemarkungen``, and a German
        ``message`` the UI can show as-is.

    Raises:
        HTTPException: If there's an error fetching Flurstueck data.
    """
    try:
        page = HamburgOGCAPI.fetch_data(
            str(api_settings.FLURSTUECKE_API_URL),
            {
                "f": "json",
                "bbox": f"{bbox.min_x},{bbox.min_y},{bbox.max_x},{bbox.max_y}",
                "limit": HamburgOGCAPI.DEFAULT_LIMIT,
                "skipGeometry": "true",
            },
        )
        gemarkungen = sorted(
            {
                name
                for feature in page.get("features") or []
                if (name := (feature.get("properties") or {}).get("gemarkung"))
            }
        )
        count = page.get("numberMatched", len(page.get("features") or []))
        label = "Flurstück" if count == 1 else "Flurstücke"
        message = f"{count} {label}"
        if gemarkungen:
            message = f"{message} in {', '.join(gemarkungen)}"
        return JSONResponse(
            content={
                "count": count,
                "gemarkungen": gemarkungen,
                "message": message,
            }
        )
    except Exception as e:
        LOGGER.error("An error occurred: %s" % e)
        raise HTTPException(
            status_code=500, detail=f"Error fetching Flurstueck data: {str(e)}"
        )


@router.get(
    "/bimfabrikhh-datasets/wfs-boreholes",
    response_class=Response,
    tags=["Baugrundaufschlüsse Hamburg"],
    description="Count Hamburg Baugrundaufschlüsse from the BoreholeML 3.0 Header WFS",
)
def get_wfs_boreholes(bbox: BoundingBoxParams = Depends()) -> JSONResponse:
    """
    Count boreholes in the umring for the BIMFabrik workflow preview.

    Uses the Header WFS (stammdaten only), like the Flurstücke preview:
    a German ``message`` the UI can show as-is, without soil layers.

    Args:
        bbox: Bounding box parameters defining the area of interest.

    Returns:
        JSONResponse: ``count``, optional ``projekte``, and a German
        ``message`` such as ``129 Bohrungen wurden gefunden``.

    Raises:
        HTTPException: If there's an error fetching borehole header data.
    """
    try:
        bbox_dict = {
            "min_x": bbox.min_x,
            "min_y": bbox.min_y,
            "max_x": bbox.max_x,
            "max_y": bbox.max_y,
        }
        xml_root = DataFetcher.fetch_borehole_header_data(bbox_dict)
        count, projekte = _borehole_header_preview(xml_root)
        if count == 1:
            message = "1 Bohrung wurde gefunden"
        else:
            message = f"{count} Bohrungen wurden gefunden"
        return JSONResponse(
            content={
                "count": count,
                "projekte": projekte,
                "message": message,
            }
        )
    except Exception as e:
        LOGGER.error("An error occurred: %s" % e)
        raise HTTPException(
            status_code=500, detail=f"Error fetching borehole data: {str(e)}"
        )


def _borehole_header_preview(
    xml_root: etree._Element | None,
) -> tuple[int, list[str]]:
    """Count Header features and collect unique project names."""
    if xml_root is None:
        return 0, []
    headers = xml_root.xpath(
        "//bmlh:BoreholeHeader",
        namespaces={"bmlh": BMLH_NS},
    )
    projekte = sorted(
        {
            (project or "").strip()
            for header in headers
            if (project := header.findtext(f"{{{BMLH_NS}}}project"))
        }
    )
    return len(headers), projekte


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
