# BIMFabrikHH_ogc.py - This is your main file

import uvicorn
from fastprocesses.api.server import OGCProcessesAPI

# Import the process classes - this is crucial for registration
from processes.simple_process import SimpleProcess
from processes.uppercase_process import UppercaseProcess
from processes.number_process import NumberProcess

# Create the API application
app = OGCProcessesAPI(
    title="Multiple Processes API",
    description="API for various data processing tasks",
    version="1.0.0",
)

if __name__ == "__main__":
    uvicorn.run(app.get_app(), host="127.0.0.1", port=8000)
