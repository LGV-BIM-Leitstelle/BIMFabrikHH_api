# processes/simple_process.py

from typing import Dict
from fastprocesses.core.base_process import BaseProcess
from fastprocesses.core.models import (
    ProcessDescription,
    ProcessInput,
    ProcessOutput,
    Schema,
    ProcessJobControlOptions,
    ProcessOutputTransmission,
)
from fastprocesses.processes.process_registry import register_process


@register_process("simple_process")
class SimpleProcess(BaseProcess):
    process_description = ProcessDescription(
        id="simple_process",
        title="Simple Process",
        version="1.0.0",
        description="A simple example process",
        jobControlOptions=[ProcessJobControlOptions.SYNC_EXECUTE, ProcessJobControlOptions.ASYNC_EXECUTE],
        outputTransmission=[ProcessOutputTransmission.VALUE],
        inputs={
            "input_text": ProcessInput(
                title="Input Text",
                description="Text to process",
                scheme=Schema(type="string", minLength=1, maxLength=1000),
            )
        },
        outputs={
            "output_text": ProcessOutput(
                title="Output Text",
                description="Processed text",
                scheme=Schema(type="string"),
            )
        },
    )

    async def execute(self, inputs: Dict) -> Dict:
        input_text = inputs["inputs"]["input_text"]
        return {"output_text": input_text.upper()}
