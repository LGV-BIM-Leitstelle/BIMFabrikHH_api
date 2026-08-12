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


def rate_limit_enabled() -> bool:
    """Return whether per-client request rate limiting is active.

    Rate limiting is an opt-in subset of admission control. It requires both:

    * Admission control to be active (Redis backend, see
      :func:`admission_control_enabled`), and
    * The independent ``ENABLE_RATE_LIMIT`` flag to be truthy
      (e.g. ``true``/``1``/``yes``).

    This lets the production server (Redis backend) keep the per-client
    concurrency limit while turning request rate limiting off. Defaults to
    disabled.

    Evaluated at call time so it reflects the ``BACKEND_DB`` and
    ``ENABLE_RATE_LIMIT`` values set at runtime.
    """
    flag_enabled = os.getenv("ENABLE_RATE_LIMIT", "false").lower() in (
        "true",
        "1",
        "yes",
    )
    return admission_control_enabled() and flag_enabled


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

    # Admission control - rate limiting (opt-in, independent of BACKEND_DB)
    ENABLE_RATE_LIMIT: bool = False
    RATE_LIMIT_TIMES: int = 5
    RATE_LIMIT_SECONDS: int = 60

    # Admission control - concurrent jobs per client identifier
    MAX_CONCURRENT_JOBS: int = 2

    # Logging configuration
    # Per-handler log levels (console and file handlers can differ).
    LOG_LEVEL_CONSOLE: str = "INFO"
    LOG_LEVEL_FILE: str = "INFO"
    # Whether the rotating file handler is attached at all.
    LOG_FILE_ENABLED: bool = True
    # Path (relative to project root or absolute) of the shared log file.
    LOG_FILE_PATH: str = "logs/bimfabrikhh.log"
    # Timed-rotation interval keyword (see TimedRotatingFileHandler ``when``),
    # e.g. "midnight", "H", "D", "S". Number of rotated files kept as backups.
    LOG_FILE_WHEN: str = "midnight"
    LOG_FILE_BACKUP_COUNT: int = 14

    @property
    def redis_url(self) -> str:
        """Return the Redis connection URL used for admission control.

        Built from the individual host/port/db settings.
        """
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    def config_summary(self) -> str:
        """Return a human-readable, multi-line summary of the active configuration.

        Intended to be logged once during API initialization so the effective
        settings (loaded from ``.env`` with defaults) are visible in the logs.
        """
        lines = [
            "BIMFabrikHH API configuration:",
            f"  Base URL:            {self.BASE_URL}",
            f"  Server:              {self.API_HOST}:{self.API_PORT}",
            f"  Trees API:           {self.TREES_API_URL}",
            f"  Trees Hafen API:     {self.TREES_HAFEN_API_URL}",
            f"  DGM tiles API:       {self.DGM_TILES_API_URL}",
            f"  API timeout:         {self.API_TIMEOUT}s",
            f"  API default limit:   {self.API_DEFAULT_LIMIT}",
            f"  API default CRS:     {self.API_DEFAULT_CRS}",
            f"  Output folder:       {self.OUTPUT_FOLDER_PATH}",
            f"  Output URL (http):   {self.URL_OUTPUT_HTTP}",
            f"  Output URL (https):  {self.URL_OUTPUT_HTTPS}",
            f"  Data base URL:       {self.DATA_BASE_URL}",
            f"  Data LoD1 folder:    {self.DATA_LOD1_FOLDER}",
            f"  Data LoD2 folder:    {self.DATA_LOD2_FOLDER}",
            f"  Data DGM folder:     {self.DATA_DGM_FOLDER}",
            f"  Backend DB:          {os.getenv('BACKEND_DB', 'sqlite').lower()}",
            f"  Admission control:   {admission_control_enabled()}",
            (
                f"  Rate limiting:       {rate_limit_enabled()} "
                f"({self.RATE_LIMIT_TIMES}/{self.RATE_LIMIT_SECONDS}s)"
            ),
            f"  Max concurrent jobs: {self.MAX_CONCURRENT_JOBS}",
            f"  Redis URL:           {self.redis_url}",
            f"  Log level (console): {self.LOG_LEVEL_CONSOLE}",
            f"  Log level (file):    {self.LOG_LEVEL_FILE}",
            f"  Log file enabled:    {self.LOG_FILE_ENABLED}",
            f"  Log file path:       {self.LOG_FILE_PATH}",
        ]
        return "\n".join(lines)


# Global settings instance
try:
    api_settings = APISettings()  # noqa
except Exception as e:
    raise RuntimeError(
        f"Failed to load settings: {e}. Make sure .env file exists and contains all required variables."
    )
