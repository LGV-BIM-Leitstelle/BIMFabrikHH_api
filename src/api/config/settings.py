"""
Pydantic settings configuration for BIMFabrikHH API.
Uses environment variables with fallback to defaults.
"""

import logging
from pathlib import Path

from pydantic import HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Get project root directory (3 levels up from this file)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class APISettings(BaseSettings):
    """API configuration settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Base Configuration
    BASE_URL: HttpUrl

    # Server Configuration
    API_HOST: str
    API_PORT: str

    # Tree API (baum app)
    TREES_API_URL: HttpUrl

    # Tree API Hafen (harbor trees)
    TREES_HAFEN_API_URL: HttpUrl

    # DGM API (dgm app)
    DGM_TILES_API_URL: HttpUrl

    # API Settings
    API_TIMEOUT: int
    API_DEFAULT_LIMIT: int
    API_DEFAULT_CRS: str

    # Output URLs for generated files
    URL_OUTPUT_HTTP: HttpUrl
    URL_OUTPUT_HTTPS: HttpUrl

    # File system paths
    OUTPUT_FOLDER_PATH: str

    # Online data source URLs (Hamburg Open Data) - Required in .env
    DATA_BASE_URL: str
    DATA_LOD1_FOLDER: str
    DATA_LOD2_FOLDER: str
    DATA_DGM_FOLDER: str


# Global settings instance
try:
    api_settings = APISettings()  # noqa
except Exception as e:
    raise RuntimeError(
        f"Failed to load settings: {e}. Make sure .env file exists and contains all required variables."
    )
