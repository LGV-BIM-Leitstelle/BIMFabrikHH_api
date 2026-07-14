"""
Pydantic settings configuration for BIMFabrikHH API.
Uses environment variables with fallback to defaults.
"""

import logging
import os
from pathlib import Path

from pydantic import HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Get project root directory (3 levels up from this file)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


def admission_control_enabled() -> bool:
    """Return whether application-level admission control is active.

    Admission control (Redis-backed rate limiting and concurrent-job limiting)
    is only enabled in production mode, i.e. when the Redis backend is selected
    via ``--db redis`` (which sets ``BACKEND_DB=redis``). For the sqlite backend
    used in local/testing runs it is disabled.

    Evaluated at call time so it reflects the ``BACKEND_DB`` value set by the
    application launcher at runtime.
    """
    return os.getenv("BACKEND_DB", "sqlite").lower() == "redis"


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

    # Redis configuration (used for admission control: rate limiting and concurrency)
    # Optional so that the sqlite/local backend runs without Redis configured.
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # Admission control - rate limiting
    RATE_LIMIT_TIMES: int = 5
    RATE_LIMIT_SECONDS: int = 60

    # Admission control - concurrent jobs per client identifier
    MAX_CONCURRENT_JOBS: int = 2

    @property
    def redis_url(self) -> str:
        """Return the Redis connection URL used for admission control.

        Built from the individual host/port/db settings.
        """
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


# Global settings instance
try:
    api_settings = APISettings()  # noqa
except Exception as e:
    raise RuntimeError(
        f"Failed to load settings: {e}. Make sure .env file exists and contains all required variables."
    )
