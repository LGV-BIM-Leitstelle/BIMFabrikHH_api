from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    accepted = "accepted"
    running = "running"
    successful = "successful"
    failed = "failed"
    dismissed = "dismissed"


class ProcessJob(BaseModel):
    id: str
    status: JobStatus
    created: str
    started: Optional[str] = None
    finished: Optional[str] = None
    message: Optional[str] = None
    progress: int = 0
    results: Optional[Dict] = None
    type: str = "process"


# class ProcessInput(BaseModel):
#     bbox: List[float] = Field(..., description="Bounding box [min_x, min_y, max_x, max_y]")
#
#     crs: str = Field("http://www.opengis.net/def/crs/EPSG/0/25832", description="Coordinate reference system")
#     limit: int = Field(2000, description="Maximum number of features to return")
#     skip_geometry: bool = Field(True, description="Skip geometry in response")
