from typing import Dict

from BIMFabrikHH.apps.baum import BaumModeller, ModelParams
from BIMFabrikHH.core.request_oaf import HamburgOGCAPI
from BIMFabrikHH.default.url_api import PathUrl
from BIMFabrikHH.pydantic_models.bounding_box import BoundingBoxParams
from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import JSONResponse

router_trees = APIRouter()
baum_modeller = BaumModeller()


@router_trees.get(
    "/oaf-trees",
    response_class=Response,
    description="Get trees from OGC API Features Hamburg"
)
def get_oaf_trees(
    min_x: float = Query(9.9733),
    min_y: float = Query(53.5544),
    max_x: float = Query(9.9756),
    max_y: float = Query(53.5556)
):
    try:
        bbox = {
            "min_x": min_x,
            "min_y": min_y,
            "max_x": max_x,
            "max_y": max_y,
        }

        url = PathUrl.URL_OAF_TREES
        params_trees = {
            "f": "json",
            "bbox": f"{bbox['min_x']},{bbox['min_y']},{bbox['max_x']},{bbox['max_y']}",
            "crs": "http://www.opengis.net/def/crs/EPSG/0/25832",
            "limit": 2000,
            # "properties": properties,
            "skipGeometry": "true",
        }

        trees_data: Dict = HamburgOGCAPI.fetch_data(url, params_trees)

        return JSONResponse(content=trees_data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching tree data: {str(e)}")


@router_trees.post(
    "/generate-tree-model",
    response_class=Response,
    description="Generate an IFC model of trees within the specified bounding box"
)
def generate_tree_model(
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
        ifc_bytes = baum_modeller.create_trees(params)
        return Response(
            content=ifc_bytes,
            media_type="application/x-step",
            headers={"Content-Disposition": f"attachment; filename=trees_{params.project_name}.ifc"}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating tree model: {str(e)}")
