"""
Database package for BIMFabrikHH API.

This package contains Celery database configuration and related utilities
for managing task persistence and job tracking.
"""

import os
from pathlib import Path
from typing import Final

# Database configuration
# Use /app/database for persistence (outside Python package to avoid volume mount conflicts)
BASE_DIR: Final[Path] = Path(os.getenv("CELERY_DB_DIR", Path.home() / ".bimfabrikhh" / "database"))
CELERY_DB_PATH: Final[str] = os.path.join(BASE_DIR, "celerydb.sqlite")
CELERY_BROKER_URL: Final[str] = f"sqla+sqlite:///{CELERY_DB_PATH}"
CELERY_BACKEND_URL: Final[str] = f"db+sqlite:///{CELERY_DB_PATH}"

# Ensure database directory exists
os.makedirs(BASE_DIR, exist_ok=True)
