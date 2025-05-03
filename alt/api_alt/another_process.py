from fastprocesses.core.base_process import BaseProcess
from fastprocesses.core.models import (ProcessDescription, ProcessInput,
                                       ProcessJobControlOptions, ProcessOutput,
                                       ProcessOutputTransmission, Schema)
from fastprocesses.processes.process_registry import register_process


@register_process("another_process")
class AnotherProcess(BaseProcess):
    process_description = ProcessDescription(
        id="another_process",
        title="Another Process",
        version="1.0.0",
        description="Another process that multiplies a number",
        jobControlOptions=[ProcessJobControlOptions.SYNC_EXECUTE, ProcessJobControlOptions.ASYNC_EXECUTE],
        outputTransmission=[ProcessOutputTransmission.VALUE],
        inputs={
            "input_number": ProcessInput(
                title="Input Number",
                description="Number to process",
                scheme=Schema(type="integer", minimum=1)
            )
        },
        outputs={
            "output_result": ProcessOutput(
                title="Output Result",
                description="Processed result",
                scheme=Schema(type="integer")
            )
        }
    )

    async def execute(self, inputs: dict) -> dict:
        input_number = inputs["inputs"]["input_number"]
        output_result = input_number * 2  # Example of multiplying the input number by 2
        return {"output_result": output_result}
