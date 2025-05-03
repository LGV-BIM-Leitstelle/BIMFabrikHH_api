from fastprocesses.api.server import OGCProcessesAPI
from simple_process import SimpleProcess

services = {"simple_process": SimpleProcess}


app = OGCProcessesAPI(
    title="OGC BIM Process API",
    version="1.0.0",
    description="A simple BIM API for running processes"
).get_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8004)
