from typing import Optional

from BIMFabrikHH.pydantic_models.params_bbox import BoundingBoxParams
from pydantic import BaseModel


class ProcessInput(BaseModel):
    bbox: BoundingBoxParams
    crs: Optional[str] = None
    limit: Optional[int] = None
    skip_geometry: Optional[bool] = None
    level_of_geom: Optional[int] = None
    project_name: Optional[str] = None
