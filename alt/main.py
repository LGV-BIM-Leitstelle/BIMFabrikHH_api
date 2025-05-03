from fastapi import FastAPI
from fastapi.responses import JSONResponse
from src.app_trees import router_trees

app = FastAPI(
    title="BIMFabrikHH API",
    description="API for creating IFC models based on GIS Data",
    version="1.0.0",
    # swagger_ui_parameters={"defaultModelsExpandDepth": 0}
)


@app.get("/", include_in_schema=False)
def get_frontpage():
    return JSONResponse(content={"message": "Server is running"})


app.include_router(router_trees, tags=["Strassenbaumkataster"])

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8001)
