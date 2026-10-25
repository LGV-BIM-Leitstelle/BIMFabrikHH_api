"""
Inputs a client sends to execute a process.

Core's ``RequestParams`` describes the CRS of the source data with
``source_epsg`` / ``vertical_epsg``. In the API the source data is always
fetched by the API itself, so those two codes are not client inputs: every
task sets them to the CRS it fetches its data in.
"""

from copy import deepcopy
from typing import List, Optional

from BIMFabrikHH_core.data_models.params_bbox import BoundingBoxParams
from BIMFabrikHH_core.data_models.params_tree import Container, RequestParams
from BIMFabrikHH_core.data_models.pydantic_georeferencing import check_projected_epsg
from pydantic import BaseModel, ConfigDict, model_validator

_API_SET_FIELDS = ("source_epsg", "vertical_epsg")
_CORE_FIELDS = RequestParams.model_fields
_CORE_EXAMPLE = RequestParams.model_config["json_schema_extra"]["example"]


class ProcessInputs(BaseModel):
    """``RequestParams`` without ``source_epsg`` and ``vertical_epsg``.

    Field definitions are taken from core. Unknown keys, including the two
    codes the API sets, are rejected.
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                key: value
                for key, value in _CORE_EXAMPLE.items()
                if key not in _API_SET_FIELDS
            }
        },
    )

    bbox: Optional[BoundingBoxParams] = deepcopy(_CORE_FIELDS["bbox"])
    containers: Optional[List[Container]] = deepcopy(_CORE_FIELDS["containers"])
    use_dgm_elevation: bool = deepcopy(_CORE_FIELDS["use_dgm_elevation"])
    output_epsg: Optional[int] = deepcopy(_CORE_FIELDS["output_epsg"])

    @model_validator(mode="after")
    def _check_output_epsg(self) -> "ProcessInputs":
        if self.output_epsg is not None:
            bbox = self.bbox
            check_projected_epsg(
                self.output_epsg,
                None if bbox is None else (bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y),
            )
        return self

    def to_request_params(
        self, source_epsg: int, vertical_epsg: Optional[int] = None
    ) -> RequestParams:
        """Core ``RequestParams`` for data the API fetched in ``source_epsg``.

        ``vertical_epsg`` is the height system of that data; ``None`` for data
        without heights.
        """
        return RequestParams(
            **self.model_dump(),
            source_epsg=source_epsg,
            vertical_epsg=vertical_epsg,
        )
