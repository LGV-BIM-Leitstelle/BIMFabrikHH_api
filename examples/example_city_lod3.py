"""Same 1.5 km × 1.5 km Innenstadt umring for city LoD3, trees, and DGM (rust).

    python examples/example_city_lod3.py
    python examples/example_city_lod3.py --base-url http://localhost:8083
"""

from __future__ import annotations

import argparse
import json
import time

import requests

# 1.5 km × 1.5 km (2.25 km² / 225 ha) Innenstadt. Inset from the 1 km grid
# so the WGS84 bbox still hits only four DK5 tiles.
# UTM 565250,5933250–566750,5934750. Tiles: 6533, 6534, 6633, 6634.
BBOX = {
    "min_x": 9.984717,
    "min_y": 53.544091,
    "max_x": 10.007670,
    "max_y": 53.557384,
}
BODY = {
    "inputs": {
        "bbox": BBOX,
        "use_dgm_elevation": False,
        "containers": [
            {
                "containerTitle": "Level of Geometry",
                "containerId": "level_of_geometry",
                "components": {
                    "level_of_geom": {"title": "LoD", "value": 3},
                },
            },
            {
                "containerTitle": "Projektinformationen",
                "containerId": "Projektinformationen",
                "components": {
                    "project": {"title": "Projektname", "value": "LoD3 Test Innenstadt"},
                    "site": {"title": "IfcSite", "value": "Hamburg"},
                    "building": {"title": "IfcBuilding", "value": "Innenstadt"},
                },
            },
        ],
    }
}
PROCESSES = (
    "generate-city-model-rs",
    "generate-tree-model-rs",
    "generate-dgm-model-rs",
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="City LoD3 + trees + DGM on the same umring"
    )
    parser.add_argument("--base-url", default="http://localhost:8083")
    parser.add_argument("--timeout", type=int, default=600, help="seconds to wait in total")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    session = requests.Session()
    session.trust_env = False

    jobs: dict[str, str] = {}
    for process in PROCESSES:
        url = f"{base}/ogc/processes/{process}/execution"
        print(f"POST {url}")
        created = session.post(url, json=BODY, timeout=30)
        if not created.ok:
            raise SystemExit(f"{process}: {created.status_code} {created.reason}\n{created.text}")
        job = created.json()
        jobs[process] = job["id"]
        print(json.dumps(job, indent=2))

    results: dict[str, object] = {}
    pending = set(jobs)
    deadline = time.monotonic() + args.timeout
    while pending:
        if time.monotonic() >= deadline:
            raise SystemExit(f"timed out, still running: {sorted(pending)}")
        for process in list(pending):
            job_id = jobs[process]
            status_resp = session.get(f"{base}/ogc/jobs/{job_id}", timeout=30)
            status_resp.raise_for_status()
            status = status_resp.json()
            state = status.get("status")
            print(f"{process}  {state}")
            if state == "successful":
                done = session.get(f"{base}/ogc/jobs/{job_id}/results", timeout=30)
                done.raise_for_status()
                results[process] = done.json()
                pending.remove(process)
            elif state == "failed":
                raise SystemExit(f"{process} failed\n{json.dumps(status, indent=2)}")
        if pending:
            time.sleep(5)

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
