"""
Database package for BIMFabrikHH API.

This package contains Celery database configuration and related utilities
for managing task persistence and job tracking.
"""

import os
from typing import Final

# Database configuration
# Use /app/database for persistence (outside Python package to avoid volume mount conflicts)
DATABASE_DIR: Final[str] = os.getenv("CELERY_DB_DIR", "/app/database")
CELERY_DB_PATH: Final[str] = os.path.join(DATABASE_DIR, "celerydb.sqlite")
CELERY_BROKER_URL: Final[str] = f"sqla+sqlite:///{CELERY_DB_PATH}"
CELERY_BACKEND_URL: Final[str] = f"db+sqlite:///{CELERY_DB_PATH}"

# Ensure database directory exists
os.makedirs(DATABASE_DIR, exist_ok=True)
