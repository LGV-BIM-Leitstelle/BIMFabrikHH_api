from typing import Dict, List

from fastapi import APIRouter, Response, HTTPException, Query
from fastapi.responses import JSONResponse

from BIMFabrikHH.apps.baum import BaumModeller, ModelParams
from BIMFabrikHH.apps.stadtmodell.app import process_gml_to_ifc
from BIMFabrikHH.core.request_oaf import HamburgOGCAPI
from BIMFabrikHH.default.url_api import PathUrl
from BIMFabrikHH.pydantic_models.bounding_box import BoundingBoxParams

router_dgm_modell = APIRouter()
baum_modeller = BaumModeller()


@router_dgm_modell.get(
    "/get-oaf-dgm-tiles",
    response_class=Response,
    description="Get Tiles-DGM from OGC API Features Hamburg",
)
def get_oaf_dgm(
    min_x: float = Query(9.9733),
    min_y: float = Query(53.5544),
    max_x: float = Query(9.9756),
    max_y: float = Query(53.5556),
):
    try:
        bbox = {
            "min_x": min_x,
            "min_y": min_y,
            "max_x": max_x,
            "max_y": max_y,
        }
        # trees_data = baum_modeller.get_oaf_trees(bbox)

        url = PathUrl.URL_OAF_TREES
        params_trees = {
            "f": "json",
            "bbox": f"{bbox['min_x']},{bbox['min_y']},{bbox['max_x']},{bbox['max_y']}",
            "crs": "http://www.opengis.net/def/crs/EPSG/0/25832",
            # "limit": 5000,
            "skipGeometry": "true",
        }

        trees_data: Dict = HamburgOGCAPI.fetch_data(url, params_trees)

        return JSONResponse(content=trees_data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching tree data: {str(e)}")


@router_dgm_modell.post(
    "/generate-dgm-model",
    response_class=Response,
    description="Generate an IFC model of Dgm within the specified bounding box",
)
async def generate_dgm_model(
    gml_files: List = Query(),
    params: ModelParams = ModelParams(
        bbox=BoundingBoxParams(
            min_x=9.9847,
            min_y=53.5519,
            max_x=9.9856,
            max_y=53.5522,
        ),
        level_of_geom=1,
        project_name="Test",
    ),
):
    try:
        ifc_bytes = process_gml_to_ifc(
            gml_files,
            "Hamburg Buildings",
            "Hamburg Site",
            reset_model=True,
        )

        return Response(
            content=ifc_bytes,
            media_type="application/x-step",
            headers={"Content-Disposition": f"attachment; filename=trees_{params.project_name}.ifc"},
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating tree model: {str(e)}")
