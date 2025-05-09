import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

from src.api.ogc_api.config.app_info import app_contact, app_description, app_license_info
from src.api.ogc_api.routes.main_ogc import router_ogc

app = FastAPI(
    title="BIMFabrikHH OGC API - Processes",
    description=app_description,
    version="1.0.0",
    contact=app_contact,
    license_info=app_license_info,
)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"]
)

app.include_router(router_ogc)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

try:
    app.mount(
        "/output",
        StaticFiles(directory="C:/Users/Public/Python/AS_BIMFabrikHH_API/BIMFabrikHH_api/output"),
        name="output",
    )
    print("Mounted static files successfully.")
except Exception as e:
    print(f"Error mounting static files: {e}")
    app.mount("/output", StaticFiles(directory=OUTPUT_DIR), name="output")
    print(f"Mounted static files from alternative path. {OUTPUT_DIR}")


if __name__ == "__main__":
    import uvicorn

    server = False
    if server:
        uvicorn.run("BIMFabrikHH_ogc:app", host="0.0.0.0", port=8084, reload=True)
    else:
        print("Starting server on localhost...")
        uvicorn.run("BIMFabrikHH_ogc:app", host="127.0.0.1", port=8084, reload=True)
