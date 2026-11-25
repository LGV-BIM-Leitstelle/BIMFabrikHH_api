"""Every OGC process at every level_of_geom it accepts, on one umring, with a log file.

Asks the running API for its processes (``/ogc/processes``) and for the
``level_of_geom`` values each one accepts (``/ogc/processes/{id}``), so new
processes and LoDs are picked up without changing this script. Processes
without ``level_of_geom`` (Flurstuecke, boreholes, basepoint) run once.
Jobs run one after another; the log file gets every job with status, time,
IFC and the failure message.

The default umring is ~280 m × 280 m (0.078 km²) at the Rathaus: inside the
0.1 km² borehole limit and inside the LoD3 area of example_city_lod3.py.
UTM 565810,5933810–566090,5934090.

    python examples/example_all_processes.py
    python examples/example_all_processes.py --process generate-dgm-model-rs
    python examples/example_all_processes.py --bbox 9.9769 53.5478 9.9814 53.5503
"""

from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from example_random_1km import ifc_from_job, why_from_job

BBOX = {
    "min_x": 9.993284,
    "min_y": 53.549054,
    "max_x": 9.997569,
    "max_y": 53.551536,
}

LOGGER = logging.getLogger("example_all_processes")


def lod_values(description: dict[str, Any]) -> list[int]:
    """``level_of_geom`` enum from a process description, empty if it has none."""
    any_of = description["inputs"]["containers"]["schema"]["items"]["anyOf"]
    for branch in any_of:
        components = branch.get("properties", {}).get("components", {}).get("properties", {})
        if "level_of_geom" in components:
            return list(components["level_of_geom"]["properties"]["value"]["enum"])
    return []


def body_for(bbox: dict[str, float], process: str, lod: int | None) -> dict[str, Any]:
    containers: list[dict[str, Any]] = [
        {
            "containerTitle": "Projektinformationen",
            "containerId": "Projektinformationen",
            "components": {
                "project": {"title": "IfcProject", "value": f"{process} LoD {lod or '-'}"},
                "site": {"title": "IfcSite", "value": "Hamburg"},
                "building": {"title": "IfcBuilding", "value": "Rathaus"},
            },
        }
    ]
    if lod is not None:
        containers.append(
            {
                "containerTitle": "Level of Geometry",
                "containerId": "level_of_geometry",
                "components": {"level_of_geom": {"title": "LoD", "value": lod}},
            }
        )
    return {"inputs": {"bbox": bbox, "containers": containers}}


def wait_job(session: requests.Session, base: str, job_id: str, timeout: float) -> tuple[str, dict[str, Any]]:
    deadline = time.monotonic() + timeout
    status: dict[str, Any] = {}
    last_state = ""
    while time.monotonic() < deadline:
        try:
            resp = session.get(f"{base}/ogc/jobs/{job_id}", timeout=30)
            resp.raise_for_status()
        except requests.RequestException as exc:
            LOGGER.warning("  poll retry after %s", exc.__class__.__name__)
            time.sleep(2)
            continue
        status = resp.json()
        state = str(status.get("status") or "")
        if state != last_state:
            LOGGER.info("  %s", state)
            last_state = state
        if state in {"successful", "failed", "dismissed"}:
            return state, status
        time.sleep(2)
    return "timeout", status


def run_job(
    session: requests.Session,
    *,
    base: str,
    bbox: dict[str, float],
    process: str,
    lod: int | None,
    timeout: int,
    output_dir: Path,
) -> dict[str, Any]:
    row: dict[str, Any] = {"process": process, "lod": lod or "-", "status": "", "seconds": 0.0, "ifc": "—", "mb": "—"}
    started = time.monotonic()
    try:
        created = session.post(f"{base}/ogc/processes/{process}/execution", json=body_for(bbox, process, lod), timeout=30)
    except requests.RequestException as exc:
        row.update(status=f"submit-error:{exc.__class__.__name__}", why=str(exc))
    else:
        if created.ok:
            job_id = created.json()["id"]
            LOGGER.info("  job %s", job_id)
            state, status = wait_job(session, base, job_id, timeout)
            row.update(status=state, why=why_from_job(status, state), job=job_id)
            row["ifc"], row["mb"] = ifc_from_job(status, output_dir)
        else:
            row.update(status=f"http-{created.status_code}", why=created.text or created.reason)
    row["seconds"] = time.monotonic() - started
    if row["status"] == "successful":
        LOGGER.info("  %s  %.1fs  %s  %s MB", row["status"], row["seconds"], row["ifc"], row["mb"])
    else:
        LOGGER.error("  %s  %.1fs  %s", row["status"], row["seconds"], row["why"])
    return row


def log_table(rows: list[dict[str, Any]]) -> None:
    headers = ("process", "lod", "status", "s", "mb", "ifc / message")
    cells = [
        (
            r["process"],
            str(r["lod"]),
            r["status"],
            f"{r['seconds']:.1f}",
            str(r["mb"]),
            r["ifc"] if r["status"] == "successful" else r["why"],
        )
        for r in rows
    ]
    widths = [max(len(h), *(len(c[i]) for c in cells)) for i, h in enumerate(headers)]

    def fmt(parts: tuple[str, ...]) -> str:
        return "  ".join(c.ljust(w) for c, w in zip(parts, widths)).rstrip()

    LOGGER.info("")
    LOGGER.info(fmt(headers))
    LOGGER.info("  ".join("-" * w for w in widths))
    for line in cells:
        LOGGER.info(fmt(line))
    ok = sum(r["status"] == "successful" for r in rows)
    LOGGER.info("%d of %d jobs successful", ok, len(rows))


def main() -> None:
    parser = argparse.ArgumentParser(description="Every process at every level_of_geom, with a log file")
    parser.add_argument("--base-url", default="http://localhost:8083")
    parser.add_argument(
        "--process",
        action="append",
        help="only these process ids (repeatable). Default: every process the API lists.",
    )
    parser.add_argument(
        "--bbox",
        nargs=4,
        type=float,
        metavar=("MIN_X", "MIN_Y", "MAX_X", "MAX_Y"),
        help="WGS84 umring. Default: Rathaus, 0.078 km².",
    )
    parser.add_argument("--timeout", type=int, default=600, help="seconds to wait per job")
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).resolve().parent.parent / "output"),
        help="API OUTPUT_FOLDER_PATH (IFC size on disk); the log file is written here too",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / f"example_all_processes_{datetime.now():%Y%m%d_%H%M%S}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-5s %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(log_path, encoding="utf-8")],
    )

    base = args.base_url.rstrip("/")
    bbox = dict(zip(("min_x", "min_y", "max_x", "max_y"), args.bbox)) if args.bbox else BBOX
    session = requests.Session()
    session.trust_env = False

    listed = session.get(f"{base}/ogc/processes", timeout=30)
    listed.raise_for_status()
    processes = args.process or [p["id"] for p in listed.json()["processes"]]
    jobs: list[tuple[str, int | None]] = []
    for process in processes:
        described = session.get(f"{base}/ogc/processes/{process}", timeout=30)
        described.raise_for_status()
        jobs.extend((process, lod) for lod in lod_values(described.json()) or [None])

    LOGGER.info("API %s  bbox %s", base, bbox)
    LOGGER.info("%d processes, %d jobs  log %s", len(processes), len(jobs), log_path.resolve())
    rows = []
    for i, (process, lod) in enumerate(jobs, start=1):
        LOGGER.info("[%d/%d] %s  LoD %s", i, len(jobs), process, lod or "-")
        rows.append(
            run_job(session, base=base, bbox=bbox, process=process, lod=lod, timeout=args.timeout, output_dir=output_dir)
        )
    log_table(rows)
    LOGGER.info("IFC folder %s", output_dir.resolve())


if __name__ == "__main__":
    main()
