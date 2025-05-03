# processes/uppercase_process.py

from typing import Dict

from fastprocesses.core.base_process import BaseProcess
from fastprocesses.core.models import (ProcessDescription, ProcessInput,
                                       ProcessJobControlOptions, ProcessOutput,
                                       ProcessOutputTransmission, Schema)
from fastprocesses.processes.process_registry import register_process


@register_process("uppercase_process")
class UppercaseProcess(BaseProcess):
    process_description = ProcessDescription(
        id="uppercase_process",
        title="Uppercase Process",
        version="1.0.0",
        description="Converts text to uppercase",
        jobControlOptions=[ProcessJobControlOptions.SYNC_EXECUTE, ProcessJobControlOptions.ASYNC_EXECUTE],
        outputTransmission=[ProcessOutputTransmission.VALUE],
        inputs={
            "input_text": ProcessInput(
                title="Input Text",
                description="Text to convert to uppercase",
                scheme=Schema(type="string", minLength=1, maxLength=1000)
            )
        },
        outputs={
            "output_text": ProcessOutput(
                title="Output Text",
                description="Uppercase text",
                scheme=Schema(type="string")
            )
        }
    )

    async def execute(self, inputs: Dict) -> Dict:
        input_text = inputs["inputs"]["input_text"]
        return {"output_text": input_text.upper()}
