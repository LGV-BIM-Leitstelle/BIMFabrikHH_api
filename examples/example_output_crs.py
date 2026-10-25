"""Every process twice: in the source CRS and transformed to ``output_epsg``.

Without ``output_epsg`` the model stays in the CRS the API fetched the data in
(EPSG:25832); with it, positions are transformed and the IFC header names the
new CRS. Heights are never transformed. The default target is EPSG:10285
(ETRS89/DREF91/2016 / Gauss-Krüger zone 3). Each IFC is downloaded and its
``IfcProjectedCRS`` name and first absolute point are printed.

    python examples/example_output_crs.py
    python examples/example_output_crs.py --base-url http://localhost:8083
    python examples/example_output_crs.py --output-epsg 31467
    python examples/example_output_crs.py --process generate-tree-model-rs
"""

from __future__ import annotations

import argparse
import re
import time
from typing import Optional

import requests

# ~220 m × 155 m Innenstadt (Valentinskamp), below the borehole area cap so
# one umring serves every process.
BBOX = {
    "min_x": 9.9756,
    "min_y": 53.5522,
    "max_x": 9.9789,
    "max_y": 53.5536,
}
PROCESSES = (
    "generate-tree-model",
    "generate-tree-model-rs",
    "generate-city-model",
    "generate-city-model-rs",
    "generate-dgm-model",
    "generate-dgm-model-rs",
    "generate-flurstuecke-model",
    "generate-boreholes-model",
)
PROJECTED_CRS = re.compile(r"IFCPROJECTEDCRS\('([^']*)'")
POINT_3D = re.compile(r"IFCCARTESIANPOINT\(\(([-\d.E]+),([-\d.E]+),([-\d.E]+)\)\)")


def body_for(output_epsg: Optional[int]) -> dict:
    inputs: dict = {"bbox": BBOX, "containers": []}
    if output_epsg is not None:
        inputs["output_epsg"] = output_epsg
    return {"inputs": inputs}


def wait_for_result(session: requests.Session, base: str, job_id: str, timeout: int) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = session.get(f"{base}/ogc/jobs/{job_id}", timeout=30)
        status.raise_for_status()
        state = status.json().get("status")
        if state == "successful":
            result = session.get(f"{base}/ogc/jobs/{job_id}/results", timeout=30)
            result.raise_for_status()
            return result.json()
        if state in {"failed", "dismissed"}:
            return {"message": f"{state}: {status.json().get('message')}"}
        time.sleep(3)
    return {"message": "timed out"}


def georeferencing(session: requests.Session, url: str) -> str:
    ifc = session.get(url, timeout=120)
    ifc.raise_for_status()
    crs = PROJECTED_CRS.search(ifc.text)
    name = crs.group(1) if crs else "no IfcProjectedCRS"
    # Coordinates are absolute, so the first point away from the local origin
    # shows the transformation; Z stays the same in both runs.
    points = ((float(x), float(y), float(z)) for x, y, z in POINT_3D.findall(ifc.text))
    point = next((p for p in points if abs(p[0]) > 1000), None)
    if point is None:
        return name
    return f"{name}  first point E={point[0]:.2f} N={point[1]:.2f} Z={point[2]:.2f}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run every process in the source CRS and in output_epsg"
    )
    parser.add_argument("--base-url", default="http://localhost:8083")
    parser.add_argument("--output-epsg", type=int, default=10285)
    parser.add_argument(
        "--process",
        action="append",
        choices=PROCESSES,
        dest="processes",
        help="Run only this process (repeatable). Default: all.",
    )
    parser.add_argument("--timeout", type=int, default=600, help="seconds to wait per job")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    session = requests.Session()
    session.trust_env = False

    jobs: dict[tuple[str, Optional[int]], str] = {}
    for process in args.processes or PROCESSES:
        for output_epsg in (None, args.output_epsg):
            created = session.post(
                f"{base}/ogc/processes/{process}/execution",
                json=body_for(output_epsg),
                timeout=30,
            )
            if not created.ok:
                raise SystemExit(f"{process}: {created.status_code}\n{created.text}")
            jobs[process, output_epsg] = created.json()["id"]
            print(f"submitted {process}  output_epsg={output_epsg}")

    for (process, output_epsg), job_id in jobs.items():
        result = wait_for_result(session, base, job_id, args.timeout)
        outcome = (
            georeferencing(session, result["url-http"])
            if "url-http" in result
            else result.get("message")
        )
        print(f"{process:28} output_epsg={str(output_epsg):6} {outcome}")


if __name__ == "__main__":
    main()
