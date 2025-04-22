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

    try:
        uvicorn.run("BIMFabrikHH_ogc:app", host="0.0.0.0", port=8083, reload=False)
    except Exception as e:
        print(f"Error starting server: {e}")
        # Fallback to localhost
        print("Starting server on localhost...")
        uvicorn.run("BIMFabrikHH_ogc:app", host="127.0.0.1", port=8083, reload=False)
