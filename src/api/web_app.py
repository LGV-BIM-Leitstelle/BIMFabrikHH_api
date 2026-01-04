"""
BIMFabrikHH API - Main application module.

This module provides the main FastAPI application for the BIMFabrikHH API,
combining both data API and OGC API services. It sets up the application
with proper middleware, routing, and static file serving.

Copyright (C) 2025 Freie und Hansestadt Hamburg, Landesbetrieb Geoinformation und Vermessung
BIM-Leitstelle, Ahmed Salem <ahmed.salem@gv.hamburg.de>
"""

import os

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

from .data_api.oaf_endpoints import router as oaf_router
from .ogc_api.ogc_metadata.app_info import (
    app_contact,
    app_data_description,
    app_license_info,
    app_ogc_description,
)
from .ogc_api.routes.main_ogc import router_ogc


def create_app() -> FastAPI:
    """
    Create and configure the main FastAPI application.

    This function sets up the combined API with both data and OGC services,
    configures CORS middleware, mounts static files, and includes all routers.

    Returns:
        FastAPI: The configured main application instance.

    Raises:
        RuntimeError: If required directories (output, static) do not exist.
    """
    # Data API
    data_app = FastAPI(title="BIMFabrikHH API", description=app_data_description, version="0.1.0")

    # OGC API Processes
    ogc_app = FastAPI(
        title="BIMFabrikHH OGC API - Processes",
        description=app_ogc_description,
        version="0.1.0",
        contact=app_contact,
        license_info=app_license_info,
    )

    # Add CORS middleware to both apps
    for api_app in [data_app, ogc_app]:
        api_app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Include routers
    data_app.include_router(oaf_router)
    ogc_app.include_router(router_ogc)

    # Static files setup for OGC app
    from .config.settings import api_settings
    from pathlib import Path
    
    # Get project root directory (this file is in src/api/)
    project_root = Path(__file__).parent.parent.parent
    output_dir = project_root / api_settings.OUTPUT_FOLDER_PATH
    static_dir = project_root / "static"

    # Check if output directory exists
    if not output_dir.exists():
        raise RuntimeError(f"Output directory does not exist: {output_dir}")

    # Check if static directory exists
    if not static_dir.exists():
        raise RuntimeError(f"Static directory does not exist: {static_dir}")

    # Create the main app and mount both sub-apps
    main_app = FastAPI(
        title="BIMFabrikHH API",
        description="Combined API with Data and OGC services",
        version="0.1.0",
    )

    # Add CORS to main app
    main_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount static files on main app
    try:
        main_app.mount("/output", StaticFiles(directory=str(output_dir)), name="output")
        print(f"Mounted output files successfully from: {output_dir}")
    except Exception as e:
        print(f"Error mounting output directory: {e}")

    try:
        main_app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        print(f"Mounted static files successfully from: {static_dir}")
    except Exception as e:
        print(f"Error mounting static directory: {e}")

    @main_app.get("/", response_class=HTMLResponse)
    async def custom_root() -> HTMLResponse:
        """
        Serve the main landing page.

        Returns:
            HTMLResponse: The HTML content of the landing page.
        """
        template_path = project_root / "templates" / "index.html"
        with open(template_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())

    # Mount sub-apps
    main_app.mount("/data", data_app)
    main_app.mount("/ogc", ogc_app)

    return main_app


def main() -> None:
    """
    Start the BIMFabrikHH API web server.

    Starts the FastAPI application using uvicorn with host and port
    configuration from environment variables. This function is called
    by the main application launcher.
    """
    import uvicorn
    from .config.settings import api_settings

    # Get configuration from settings (which loads from .env)
    port = int(api_settings.API_PORT)
    host = api_settings.API_HOST
    
    # Override host for Docker containers
    if os.getenv("DOCKER_CONTAINER", "false").lower() == "true":
        host = "0.0.0.0"

    print("Starting BIMFabrikHH API...")
    print(f"Server will run on: http://{host}:{port}")
    print(f"Data API docs: http://{host}:{port}/data/docs")
    print(f"OGC API docs: http://{host}:{port}/ogc/docs")

    app = create_app()
    uvicorn.run(app, host=host, port=port)
