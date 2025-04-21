from typing import Dict, Any

import uvicorn
from fastprocesses.api.server import OGCProcessesAPI
from fastprocesses.core.base_process import BaseProcess
from fastprocesses.core.models import (
    ProcessDescription,
    ProcessInput,
    ProcessJobControlOptions,
    ProcessOutput,
    ProcessOutputTransmission,
    Schema,
)
from fastprocesses.processes.process_registry import register_process


# First process
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
                schema=Schema(type="string", minLength=1, maxLength=1000),
            )
        },
        outputs={
            "output_text": ProcessOutput(
                title="Output Text", description="Uppercase text", schema=Schema(type="string")
            )
        },
        keywords=["text", "uppercase"],
        metadata={"created": "2024-04-08", "provider": "Example Organization"},
    )

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        input_text = inputs["inputs"]["input_text"]
        output_text = input_text.upper()
        return {"output_text": output_text}


# Second process
@register_process("lowercase_process")
class LowercaseProcess(BaseProcess):
    process_description = ProcessDescription(
        id="lowercase_process",
        title="Lowercase Process",
        version="1.0.0",
        description="Converts text to lowercase",
        jobControlOptions=[ProcessJobControlOptions.SYNC_EXECUTE, ProcessJobControlOptions.ASYNC_EXECUTE],
        outputTransmission=[ProcessOutputTransmission.VALUE],
        inputs={
            "input_text": ProcessInput(
                title="Input Text",
                description="Text to convert to lowercase",
                schema=Schema(type="string", minLength=1, maxLength=1000),
            )
        },
        outputs={
            "output_text": ProcessOutput(
                title="Output Text", description="Lowercase text", schema=Schema(type="string")
            )
        },
        keywords=["text", "lowercase"],
        metadata={"created": "2024-04-08", "provider": "Example Organization"},
    )

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        input_text = inputs["inputs"]["input_text"]
        output_text = input_text.lower()
        return {"output_text": output_text}


# Third process - combining the first two processes
@register_process("text_counter_process")
class TextCounterProcess(BaseProcess):
    process_description = ProcessDescription(
        id="text_counter_process",
        title="Text Counter Process",
        version="1.0.0",
        description="Counts characters, words, and lines in text",
        jobControlOptions=[ProcessJobControlOptions.SYNC_EXECUTE, ProcessJobControlOptions.ASYNC_EXECUTE],
        outputTransmission=[ProcessOutputTransmission.VALUE],
        inputs={
            "input_text": ProcessInput(
                title="Input Text",
                description="Text to analyze",
                schema=Schema(type="string", minLength=1, maxLength=10000),
            )
        },
        outputs={
            "char_count": ProcessOutput(
                title="Character Count", description="Number of characters", schema=Schema(type="integer")
            ),
            "word_count": ProcessOutput(
                title="Word Count", description="Number of words", schema=Schema(type="integer")
            ),
            "line_count": ProcessOutput(
                title="Line Count", description="Number of lines", schema=Schema(type="integer")
            ),
        },
        keywords=["text", "analysis", "count"],
        metadata={"created": "2024-04-08", "provider": "Example Organization"},
    )

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        input_text = inputs["inputs"]["input_text"]

        char_count = len(input_text)
        word_count = len(input_text.split())
        line_count = len(input_text.splitlines()) or 1  # At least 1 line

        return {"char_count": char_count, "word_count": word_count, "line_count": line_count}


# Main application setup
app = OGCProcessesAPI(
    title="FastProcesses API",
    description="API for various data processing tasks...",
    version="1.0.0",
)

if __name__ == "__main__":
    uvicorn.run(app.get_app(), host="127.0.0.1", port=8000)
