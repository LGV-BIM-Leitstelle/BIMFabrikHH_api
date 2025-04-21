from typing import List

from BIMFabrikHH.core.request_oaf import HamburgOGCAPI
from BIMFabrikHH.pydantic_models.params_bbox import BoundingBoxParams
from fastapi import APIRouter, Response, HTTPException, Depends
from fastapi.responses import JSONResponse

router_citymodell = APIRouter()


@router_citymodell.get(
    "/oaf-citymodell-tiles",
    response_class=Response,
    description="Get Tiles-Citymodell from OGC API Features Hamburg",
)
def get_oaf_citymodell(bbox: BoundingBoxParams = Depends()):
    try:
        citymodel_tiles: List = HamburgOGCAPI.get_tiles(x1=bbox.min_x, y1=bbox.min_y, x2=bbox.max_x, y2=bbox.max_y)

        return JSONResponse(content=citymodel_tiles)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching citymodel tiles: {str(e)}")
