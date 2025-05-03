from typing import List

from BIMFabrikHH.apps.baum import ModelParams
from BIMFabrikHH.apps.stadtmodell.app import process_gml_to_ifc
from BIMFabrikHH.core.request_oaf import HamburgOGCAPI
from BIMFabrikHH.pydantic_models.params_bbox import BoundingBoxParams
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse

router_citymodell = APIRouter()


@router_citymodell.get(
    "/oaf-citymodell-tiles",
    response_class=Response,
    description="Get Tiles-Citymodell from OGC API Features Hamburg"
)
def get_oaf_citymodell(bbox: BoundingBoxParams = Depends()):
    try:
        citymodel_tiles: List = HamburgOGCAPI.get_tiles(x1=bbox.min_x, y1=bbox.min_y, x2=bbox.max_x, y2=bbox.max_y)

        return JSONResponse(content=citymodel_tiles)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching citymodel tiles: {str(e)}")


@router_citymodell.post(
    "/generate-city-model",
    response_class=Response,
    description="Generate an IFC model of Citymodell within the specified bounding box"
)
def generate_city_model(
    gml_files: List = Query(),
    params: ModelParams = ModelParams(
        bbox=BoundingBoxParams(
            min_x=9.9847,
            min_y=53.5519,
            max_x=9.9856,
            max_y=53.5522
        ),
        level_of_geom=1,
        project_name="Test"
    )
):
    try:
        ifc_bytes = process_gml_to_ifc(
            gml_files,
            "Hamburg Buildings",
            "Hamburg Site",
            reset_model=True
        )

        return Response(
            content=ifc_bytes,
            media_type="application/x-step",
            headers={"Content-Disposition": f"attachment; filename=trees_{params.project_name}.ifc"}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating tree model: {str(e)}")
