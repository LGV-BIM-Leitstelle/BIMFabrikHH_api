# processes/number_process.py

from typing import Dict

from fastprocesses.core.base_process import BaseProcess
from fastprocesses.core.models import (ProcessDescription, ProcessInput,
                                       ProcessJobControlOptions, ProcessOutput,
                                       ProcessOutputTransmission, Schema)
from fastprocesses.processes.process_registry import register_process


@register_process("number_process")
class NumberProcess(BaseProcess):
    process_description = ProcessDescription(
        id="number_process",
        title="Number Process",
        version="1.0.0",
        description="Processes a number by multiplying it",
        jobControlOptions=[ProcessJobControlOptions.SYNC_EXECUTE, ProcessJobControlOptions.ASYNC_EXECUTE],
        outputTransmission=[ProcessOutputTransmission.VALUE],
        inputs={
            "input_number": ProcessInput(
                title="Input Number",
                description="Number to process",
                scheme=Schema(type="integer", minimum=1)
            ),
            "multiplier": ProcessInput(
                title="Multiplier",
                description="Number to multiply by",
                scheme=Schema(type="integer", minimum=1)
            ),
        },
        outputs={
            "result": ProcessOutput(
                title="Result",
                description="Multiplication result",
                scheme=Schema(type="integer")
            )
        }
    )

    async def execute(self, inputs: Dict) -> Dict:
        input_number = inputs["inputs"]["input_number"]
        multiplier = inputs["inputs"]["multiplier"]
        result = input_number * multiplier
        return {"result": result}
