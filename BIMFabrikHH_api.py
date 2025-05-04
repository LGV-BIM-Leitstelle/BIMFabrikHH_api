from fastapi import FastAPI
from fastapi.responses import JSONResponse
from src.api.data_api.oaf_endpoints import router as oaf_router
from starlette.middleware.cors import CORSMiddleware

app = FastAPI(title="BIMFabrikHH API", description="API for creating IFC models based on GIS Data", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.get("/", include_in_schema=False)
def get_frontpage():
    return JSONResponse(content={"message": "Server is running"})


app.include_router(oaf_router)


if __name__ == "__main__":
    import uvicorn

    # uvicorn BIMFabrikHH_api:app --reload

    server = False
    if server:
        uvicorn.run("BIMFabrikHH_api:app", host="0.0.0.0", port=8083, reload=True)
    else:
        print("Starting server on localhost...")
        uvicorn.run("BIMFabrikHH_api:app", host="127.0.0.1", port=8083, reload=True)
