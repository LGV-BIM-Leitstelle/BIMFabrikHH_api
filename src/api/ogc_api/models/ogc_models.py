"""
OGC API data models.

This module defines the data models used in the OGC API implementation,
including job status tracking and process parameters.
"""

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """
    Enumeration of possible job processing states.

    Attributes:
        accepted: Job has been accepted but not started.
        running: Job is currently being processed.
        successful: Job completed successfully.
        failed: Job failed during processing.
        dismissed: Job was dismissed before completion.
    """

    accepted = "accepted"
    running = "running"
    successful = "successful"
    failed = "failed"
    dismissed = "dismissed"


class ProcessJob(BaseModel):
    """
    Model representing an OGC process job.

    Attributes:
        id: Unique identifier for the job.
        status: Current status of the job.
        created: Timestamp when the job was created.
        started: Optional timestamp when the job started processing.
        finished: Optional timestamp when the job finished processing.
        message: Optional status or error message.
        progress: Processing progress as percentage (0-100).
        results: Optional dictionary containing job results.
        type: Type of the job, defaults to "process".
    """

    id: str
    status: JobStatus
    created: str
    started: Optional[str] = None
    finished: Optional[str] = None
    message: Optional[str] = None
    progress: int = 0
    results: Optional[Dict] = None
    type: str = "process"


class ProcessInput(BaseModel):
    """
    Model for OGC process input parameters.

    Attributes:
        bbox: Bounding box coordinates [min_x, min_y, max_x, max_y].
        crs: Coordinate reference system identifier.
        limit: Maximum number of features to return.
        skip_geometry: Whether to skip geometry in response.
    """

    bbox: List[float] = Field(
        ..., description="Bounding box [min_x, min_y, max_x, max_y]"
    )
    crs: str = Field(
        "http://www.opengis.net/def/crs/EPSG/0/25832",
        description="Coordinate reference system",
    )
    limit: int = Field(2000, description="Maximum number of features to return")
    skip_geometry: bool = Field(True, description="Skip geometry in response")

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "bbox": [565000.0, 5932000.0, 566000.0, 5933000.0],
                "crs": "http://www.opengis.net/def/crs/EPSG/0/25832",
                "limit": 2000,
                "skip_geometry": True,
            }
        }
