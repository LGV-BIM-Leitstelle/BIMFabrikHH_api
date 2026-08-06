"""
BIMFabrikHH API - Main application module.

This module provides the main FastAPI application for the BIMFabrikHH API,
combining both data API and OGC API services. It sets up the application
with proper middleware, routing, and static file serving.

Copyright (C) 2025 Freie und Hansestadt Hamburg, Landesbetrieb Geoinformation und Vermessung
BIM-Leitstelle, Ahmed Salem <ahmed.salem@gv.hamburg.de>, Polichronis Muratidis <polichronis.muratidis@gv.hamburg.de>
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

from .config.logging_config import setup_logging
from .config.settings import rate_limit_enabled
from .data_api.oaf_endpoints import router as oaf_router
from .ogc_api.ogc_metadata.app_info import (
    app_contact,
    app_data_description,
    app_license_info,
    app_ogc_description,
)
from .ogc_api.routes.main_ogc import router_ogc
from .ogc_api.services.rate_limit import close_rate_limiter, init_rate_limiter

logger = logging.getLogger(__name__)


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
    # Ensure logging is configured before anything emits log records.
    setup_logging()

    # Data API
    data_app = FastAPI(
        title="BIMFabrikHH API", description=app_data_description, version="0.1.0"
    )

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

    # Lifespan context manager for rate limiter
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Manage startup and shutdown of the rate limiter.

        The Redis-backed rate limiter is only initialized when rate limiting is
        enabled (Redis backend *and* ``ENABLE_RATE_LIMIT`` set); otherwise it is
        skipped and the rate limit dependency self-disables. The per-client
        concurrency limit is unaffected and runs independently.
        """
        # --- startup ---
        if rate_limit_enabled():
            try:
                await init_rate_limiter()
            except Exception as e:  # pragma: no cover - defensive startup logging
                logger.error("Error initializing rate limiter: %s", e)
        else:
            logger.info("Rate limiting disabled; skipping rate limiter init")

        yield

        # --- shutdown ---
        try:
            await close_rate_limiter()
        except Exception as e:  # pragma: no cover - defensive shutdown logging
            logger.error("Error closing rate limiter: %s", e)

    # Static files setup for OGC app
    from pathlib import Path

    from .config.settings import api_settings

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
        lifespan=lifespan,
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
        logger.info("Mounted output files successfully from: %s", output_dir)
    except Exception as e:
        logger.error("Error mounting output directory: %s", e)

    try:
        main_app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        logger.info("Mounted static files successfully from: %s", static_dir)
    except Exception as e:
        logger.error("Error mounting static directory: %s", e)

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

    # Configure logging before uvicorn starts so its loggers use our config.
    setup_logging()

    # Get configuration from settings (which loads from .env)
    port = int(api_settings.API_PORT)
    host = api_settings.API_HOST

    # Override host for Docker containers
    if os.getenv("DOCKER_CONTAINER", "false").lower() == "true":
        host = "0.0.0.0"

    logger.info("Starting BIMFabrikHH API...")
    logger.info("Server will run on: http://%s:%s", host, port)
    logger.info("Data API docs: http://%s:%s/data/docs", host, port)
    logger.info("OGC API docs: http://%s:%s/ogc/docs", host, port)

    app = create_app()
    # Pass log_config=None so uvicorn keeps our root logging configuration
    # instead of installing its own.
    uvicorn.run(app, host=host, port=port, log_config=None)


if __name__ == "__main__":
    main()
