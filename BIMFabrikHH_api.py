from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.api.data_api.citymodell import router_citymodell
from src.api.data_api.terrain import router_dgm_modell
from src.api.data_api.trees import router_trees

app = FastAPI(
    title="BIMFabrikHH API",
    description="API for creating IFC models based on GIS Data",
    version="1.0.0",
)


@app.get("/", include_in_schema=False)
def get_frontpage():
    return JSONResponse(
        content={
            "message": "Server is running",
        }
    )


app.include_router(router_trees, tags=["Strassenbaumkataster Hamburg"])
app.include_router(router_citymodell, tags=["Stadtmodell Hamburg"])
app.include_router(router_dgm_modell, tags=["Digitales Höhenmodell Hamburg DGM 1"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.1", port=8003)
    # uvicorn.run(app, host="127.0.0.1", port=8003)

    # uvicorn BIMFabrikHH_api:processes --host 127.0.0.1 --port 8003 --reload
