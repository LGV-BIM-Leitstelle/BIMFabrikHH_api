"""
Database package for BIMFabrikHH API.

This package contains Celery database configuration and related utilities
for managing task persistence and job tracking.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal


@dataclass
class CeleryConfig:
    broker_url: Final[str]
    backend_url: Final[str]


def get_celery_config() -> CeleryConfig:
    db_type: Literal["sqlite", "redis"] = str(os.getenv("BACKEND_DB", "sqlite"))

    print(f"DB TYPE set to: {db_type}")

    if db_type == "redis":
        # Redis configuration
        REDIS_HOST: Final[str] = os.getenv("REDIS_HOST", "localhost")
        REDIS_PORT: Final[str] = os.getenv("REDIS_PORT", "6379")
        REDIS_DB: Final[int] = int(os.getenv("REDIS_DB", "0"))
        REDIS_URL: Final[str] = os.getenv(
            "REDIS_URL", f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
        )
        return CeleryConfig(broker_url=REDIS_URL, backend_url=REDIS_URL)

    # Database configuration
    # Use /app/database for persistence (outside Python package to avoid volume mount conflicts)
    BASE_DIR: Final[Path] = Path(
        os.getenv("CELERY_DB_DIR", Path.home() / ".bimfabrikhh" / "database")
    )
    # Ensure database directory exists
    os.makedirs(BASE_DIR, exist_ok=True)

    CELERY_DB_PATH: Final[str] = os.path.join(BASE_DIR, "celerydb.sqlite")

    return CeleryConfig(
        broker_url=f"sqla+sqlite:///{CELERY_DB_PATH}",
        backend_url=f"db+sqlite:///{CELERY_DB_PATH}",
    )
