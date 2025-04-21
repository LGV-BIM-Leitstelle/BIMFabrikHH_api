import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.api.ogc_api.config.app_info import app_description, app_contact, app_license_info
from src.api.ogc_api.routes.main_ogc import (
    router_ogc_landingpage,
    router_ogc_joblist,
    router_ogc_conformance,
    router_ogc_processes,
    router_ogc_result,
    router_ogc_status,
)

app = FastAPI(
    title="BIMFabrikHH OGC API - Processes",
    description=app_description,
    version="1.0.0",
    contact=app_contact,
    license_info=app_license_info,
)

app.include_router(router_ogc_landingpage)
app.include_router(router_ogc_conformance)
app.include_router(router_ogc_processes)
app.include_router(router_ogc_joblist)
app.include_router(router_ogc_status)
app.include_router(router_ogc_result)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
print(OUTPUT_DIR)

app.mount("/output", StaticFiles(directory=OUTPUT_DIR), name="output")


if __name__ == "__main__":
    import uvicorn

    # uvicorn.run(app, host="127.0.0.1", port=8004, reload=True)
    # uvicorn.run("BIMFabrikHH_ogc:app", host="127.0.0.1", port=8004, reload=True)
    uvicorn.run("BIMFabrikHH_ogc:app", host="0.0.0.1", port=8004, reload=True)
