from BIMFabrikHH.apps.baum.app import BaumModeller
from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import JSONResponse

router_trees = APIRouter()
baum_modeller = BaumModeller()


@router_trees.get("/oaf-trees", response_class=Response, description="Get trees from OGC API Features Hamburg")
def get_oaf_trees(
    min_x: float = Query(9.9733),
    min_y: float = Query(53.5544),
    max_x: float = Query(9.9756),
    max_y: float = Query(53.5556),
):
    try:

        # bbox = BoundingBoxParams(min_x=min_x, min_y=min_y, max_x=max_x, max_y=max_y)

        x1 = min_x
        y1 = min_y
        x2 = max_x
        y2 = max_y

        # trees_data: Dict = baum_modeller.get_oaf_tree_df(bbox=bbox, skip_geometry=False)
        trees_data = baum_modeller.get_oaf_tree_df(x1, y1, x2, y2)
        print(trees_data)

        json_data = trees_data.to_json(orient="records")
        print(json_data)

        return JSONResponse(content=json_data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching tree data: {str(e)}")
