from typing import List

from pydantic import BaseModel, Field


class TreesInput(BaseModel):
    bbox: List[float] = Field(..., description="Bounding box [min_x, min_y, max_x, max_y]")
    crs: str = Field(
        "http://www.opengis.net/def/crs/EPSG/0/25832",
        description="Coordinate reference system"
    )
    limit: int = Field(2000, description="Maximum number of features to return")
    skip_geometry: bool = Field(True, description="Skip geometry in response")


class TreeModelInput(BaseModel):
    bbox: List[float] = Field(..., description="Bounding box [min_x, min_y, max_x, max_y]")
    level_of_geom: int = Field(1, description="Level of geometry detail (1-3)")
    project_name: str = Field("Project", description="Project name for the IFC file")
