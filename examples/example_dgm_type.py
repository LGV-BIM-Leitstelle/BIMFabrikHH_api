"""DGM with and without ALKIS Nutzung parcels (``level_of_geom``, same as city).

``level_of_geom=1`` is a single terrain mesh (default). ``level_of_geom=2`` fetches
ALKIS Nutzung from the Hamburg OAF, uses those outlines as Bruchkanten, and
writes Siedlung/Unland as one Parcels part.

Same Innenstadt / Alster umring as the core guided DGM examples
(``local_dgm.EXAMPLE_BBOX``: ``9.9769,53.5478–9.991435,53.55622``, ~0.90 km²).

    python examples/example_dgm_type.py
    python examples/example_dgm_type.py --base-url http://localhost:8083
    python examples/example_dgm_type.py --generic
    python examples/example_dgm_type.py --dgm-type 2
"""

from __future__ import annotations

import argparse
import json
import time

import requests

# Same as BIMFabrikHH_core examples/terrain/generic/local_dgm.EXAMPLE_BBOX.
BBOX = {
    "min_x": 9.9769,
    "min_y": 53.5478,
    "max_x": 9.991435,
    "max_y": 53.55622,
}

DGM_TYPE_PLAIN = 1
DGM_TYPE_PARCELS = 2
DGM_TYPE_LABELS = {
    DGM_TYPE_PLAIN: "plain (no parcels)",
    DGM_TYPE_PARCELS: "ALKIS Nutzung / parcels",
}


def body_for(dgm_type: int) -> dict:
    return {
        "inputs": {
            "bbox": BBOX,
            "containers": [
                {
                    "containerTitle": "Projektinformationen",
                    "containerId": "Projektinformationen",
                    "components": {
                        "project": {
                            "title": "Projektname",
                            "value": f"DGM type {dgm_type}",
                        },
                        "site": {"title": "IfcSite", "value": "Hamburg"},
                        "building": {"title": "IfcBuilding", "value": "Innenstadt"},
                    },
                },
                {
                    "containerTitle": "Level Of Geometry",
                    "containerId": "level_of_geometry",
                    "components": {
                        "level_of_geom": {
                            "title": "Level Of Geometry",
                            "value": dgm_type,
                        },
                    },
                },
            ],
        }
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="POST generate-dgm-model with dgm_type 1 (plain) and/or 2 (parcels)"
    )
    parser.add_argument("--base-url", default="http://localhost:8083")
    parser.add_argument(
        "--generic",
        action="store_true",
        help="Use generate-dgm-model instead of generate-dgm-model-rs",
    )
    parser.add_argument(
        "--dgm-type",
        type=int,
        choices=(DGM_TYPE_PLAIN, DGM_TYPE_PARCELS),
        action="append",
        dest="dgm_types",
        help="Run only this type (repeatable). Default: 1 then 2.",
    )
    parser.add_argument("--timeout", type=int, default=600, help="seconds to wait in total")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    process = "generate-dgm-model" if args.generic else "generate-dgm-model-rs"
    dgm_types = args.dgm_types or [DGM_TYPE_PLAIN, DGM_TYPE_PARCELS]

    session = requests.Session()
    session.trust_env = False

    jobs: dict[int, str] = {}
    started: dict[int, float] = {}
    elapsed: dict[int, float] = {}
    url = f"{base}/ogc/processes/{process}/execution"
    t0 = time.monotonic()
    for dgm_type in dgm_types:
        print(f"POST {url}  dgm_type={dgm_type}  ({DGM_TYPE_LABELS[dgm_type]})")
        started[dgm_type] = time.monotonic()
        created = session.post(url, json=body_for(dgm_type), timeout=30)
        if not created.ok:
            raise SystemExit(
                f"dgm_type={dgm_type}: {created.status_code} {created.reason}\n{created.text}"
            )
        job = created.json()
        jobs[dgm_type] = job["id"]
        print(json.dumps(job, indent=2))

    results: dict[str, object] = {}
    pending = set(jobs)
    deadline = time.monotonic() + args.timeout
    while pending:
        if time.monotonic() >= deadline:
            raise SystemExit(f"timed out, still running: {sorted(pending)}")
        for dgm_type in list(pending):
            job_id = jobs[dgm_type]
            try:
                status_resp = session.get(f"{base}/ogc/jobs/{job_id}", timeout=30)
                status_resp.raise_for_status()
            except requests.RequestException as exc:
                print(f"dgm_type={dgm_type}  poll retry after {exc.__class__.__name__}")
                continue
            status = status_resp.json()
            state = status.get("status")
            print(f"dgm_type={dgm_type}  {state}")
            if state == "successful":
                try:
                    done = session.get(f"{base}/ogc/jobs/{job_id}/results", timeout=30)
                    done.raise_for_status()
                except requests.RequestException as exc:
                    print(f"dgm_type={dgm_type}  results retry after {exc.__class__.__name__}")
                    continue
                elapsed[dgm_type] = time.monotonic() - started[dgm_type]
                print(f"dgm_type={dgm_type}  {elapsed[dgm_type]:.1f}s")
                results[f"dgm_type={dgm_type}"] = done.json()
                pending.remove(dgm_type)
            elif state == "failed":
                elapsed[dgm_type] = time.monotonic() - started[dgm_type]
                raise SystemExit(
                    f"dgm_type={dgm_type} failed after {elapsed[dgm_type]:.1f}s\n"
                    f"{json.dumps(status, indent=2)}"
                )
        if pending:
            time.sleep(5)

    print(json.dumps(results, indent=2))
    print()
    for dgm_type in dgm_types:
        print(
            f"dgm_type={dgm_type}  {DGM_TYPE_LABELS[dgm_type]}  "
            f"{elapsed[dgm_type]:.1f}s"
        )
    print(f"total  {time.monotonic() - t0:.1f}s  ({process})")


if __name__ == "__main__":
    main()
