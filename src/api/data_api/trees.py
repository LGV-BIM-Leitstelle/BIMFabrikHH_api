from typing import Dict

from BIMFabrikHH.apps.baum import BaumModeller
from BIMFabrikHH.pydantic_models.params_bbox import BoundingBoxParams
from fastapi import APIRouter, Response, HTTPException, Query
from fastapi.responses import JSONResponse

router_trees = APIRouter()
baum_modeller = BaumModeller()


@router_trees.get(
    "/oaf-trees",
    response_class=Response,
    description="Get trees from OGC API Features Hamburg",
)
def get_oaf_trees(
    min_x: float = Query(9.9733),
    min_y: float = Query(53.5544),
    max_x: float = Query(9.9756),
    max_y: float = Query(53.5556),
):
    try:

        bbox = BoundingBoxParams(
            min_x=min_x,
            min_y=min_y,
            max_x=max_x,
            max_y=max_y,
        )

        trees_data: Dict = baum_modeller.get_oaf_trees(bbox=bbox, skip_geometry=False)

        return JSONResponse(content=trees_data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching tree data: {str(e)}")
