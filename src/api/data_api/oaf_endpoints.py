from typing import List

from BIMFabrikHH.apps.baum.app import BaumModeller
from BIMFabrikHH.core.request_oaf import HamburgOGCAPI
from BIMFabrikHH.pydantic_models.params_bbox import BoundingBoxParams
from fastapi import HTTPException, Response, Depends, APIRouter
from fastapi.responses import JSONResponse
import logging
router = APIRouter()

baum_modeller = BaumModeller()

LOGGER = logging.getLogger(__name__)

@router.get(
    "/bimfabrikhh-datasets/oaf-trees",
    response_class=Response,
    tags=["Strassenbaumkataster Hamburg"],
    description="Get trees from OGC API Features Hamburg",
)
def get_oaf_trees(bbox: BoundingBoxParams = Depends()):
    try:

        trees_data: dict = baum_modeller.get_oaf_trees(bbox=bbox)

        return JSONResponse(content=trees_data)
    # TODO: Welche Fehler können hier eigentlich auftreten?
    except Exception as e:
        LOGGER.error("An error occurred: %s" % e)
        raise HTTPException(status_code=500, detail=f"Error fetching tree data: {str(e)}")


@router.get(
    "/bimfabrikhh-datasets/oaf-citymodell-tiles",  # TODO: besser: dataset/oaf-citymodell-tiles
    response_class=Response,
    tags=["Stadtmodell Hamburg"],
    description="Get Tiles-Citymodell from OGC API Features Hamburg",
)
def get_oaf_citymodell(bbox: BoundingBoxParams = Depends()):
    try:
        citymodel_tiles: List = HamburgOGCAPI.get_tiles(
            x1=bbox.min_x, y1=bbox.min_y, x2=bbox.max_x, y2=bbox.max_y, model_type="citymodel"
        ) # TODO: Wieso hier nicht direkt die bbox als Argument übergeben, wie bei get_oad_trees

        return JSONResponse(content=citymodel_tiles)
    except Exception as e:
        # TODO: Sehr breite Exception, am besten nach verschiedenen Typen auftrennen, Fehler IMMER loggen:
        LOGGER.error("An error occurred: %s" % e)
        raise HTTPException(status_code=500, detail=f"Error fetching citymodel tiles: {str(e)}")


@router.get(
    "/bimfabrikhh-datasets/get-oaf-dgm-tiles", # TODO: besser: dataset/oaf-citymodell-tiles
    response_class=Response,
    tags=["Digitales Höhenmodell Hamburg DGM 1"],
    description="Get Tiles-DGM from OGC API Features Hamburg",
)
def get_oaf_dgm(bbox: BoundingBoxParams = Depends()):
    try:
        dgm_tiles: List = HamburgOGCAPI.get_tiles(
            x1=bbox.min_x, y1=bbox.min_y, x2=bbox.max_x, y2=bbox.max_y, model_type="dgm"
        ) # TODO: Wieso hier nicht direkt die bbox als Argument übergeben?
        return JSONResponse(content=dgm_tiles)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching DGM tiles: {str(e)}")
