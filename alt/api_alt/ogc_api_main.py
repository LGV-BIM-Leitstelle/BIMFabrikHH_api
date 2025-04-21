import uvicorn
from fastprocesses.api.server import OGCProcessesAPI

app = OGCProcessesAPI(
    title="Simple Process API",
    version="1.0.0",
    description="A simple API for running processes",
).get_app()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8004)
