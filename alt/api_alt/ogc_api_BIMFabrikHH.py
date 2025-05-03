from typing import Any, Dict

import uvicorn
from BIMFabrikHH.apps.baum import BaumModeller
from BIMFabrikHH.pydantic_models.params_bbox import BoundingBoxParams
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from fastprocesses.api.server import OGCProcessesAPI
from fastprocesses.core.base_process import BaseProcess
from fastprocesses.core.models import (ProcessDescription, ProcessInput,
                                       ProcessJobControlOptions, ProcessOutput,
                                       ProcessOutputTransmission, Schema)
from fastprocesses.processes.process_registry import register_process

baum_modeller = BaumModeller()


@register_process("generate_tree_model")
class SimpleProcess(BaseProcess):
    process_description = ProcessDescription(
        id="generate_tree_model",
        title="Generate Tree Model",
        version="1.0.0",
        description="Generate an IFC model of trees within the specified bounding box",
        jobControlOptions=[ProcessJobControlOptions.SYNC_EXECUTE, ProcessJobControlOptions.ASYNC_EXECUTE],
        outputTransmission=[ProcessOutputTransmission.VALUE],
        inputs={
            "input_bbox": ProcessInput(
                title="Bounding Box",
                description="Bounding box to search for trees",
                scheme=Schema(type="object")
            )
        },
        outputs={
            "output_data": ProcessOutput(
                title="Tree Data",
                description="IFC tree model data",
                scheme=Schema(type="object")
            )
        },
        keywords=["tree", "IFC", "model"],
        metadata={"created": "2024-02-19", "provider": "Example Organization"}
    )

    async def execute(self, inputs: Dict[str, Any], **kwargs: Any):
        try:
            bbox_data = inputs.get("input_bbox")
            if not bbox_data:
                raise HTTPException(status_code=400, detail="Missing input_bbox parameter")

            # Validate input bbox with Pydantic v2
            bbox = BoundingBoxParams.model_validate(bbox_data)

            # Generate tree data
            trees_data = baum_modeller.get_oaf_trees(bbox=bbox, skip_geometry=False)

            return JSONResponse(content=trees_data)

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error fetching tree data: {str(e)}")


app = OGCProcessesAPI(
    title="Simple Process API",
    version="1.0.0",
    description="A simple API for running processes"
).get_app()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8004)
