"""Same umringe twice: generic vs rust, for tree / city / DGM.

Draws ``--count`` random ``--km`` × ``--km`` boxes (same sampling as
``bimfabrikhh_core_rs/examples/example_random_2km.py``). Each box is sent
to both the generic and the ``-rs`` process so times and IFC sizes are
comparable. Default is all three kinds (6 jobs per umring).

    python examples/example_random_1km.py --seed 1
    python examples/example_random_1km.py --km 2 --count 5 --kind tree
    python examples/example_random_1km.py --kind city --kind dgm --seed 1
"""

from __future__ import annotations

import argparse
import random
import time
from pathlib import Path
from typing import Any

import requests
from pyproj import Transformer
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Legal API clamp (BoundingBoxParams).
HAMBURG_LON = (8.421, 10.326)
HAMBURG_LAT = (53.395, 53.964)
# Same Innenstadt belt as example_random_2km.py (~8×6 km).
CENTER_EPSG = (562000.0, 5932000.0, 570000.0, 5938000.0)
# Hamburg DK5 / LoD tile extent (2 km example uses folder_extent; API has no tiles).
HAMBURG_EPSG = (548000.0, 5925000.0, 578000.0, 5950000.0)
CENTER_SHARE = 0.70
KIND_NODES = {
    "city": ("generate-city-model", "generate-city-model-rs"),
    "dgm": ("generate-dgm-model", "generate-dgm-model-rs"),
    "tree": ("generate-tree-model", "generate-tree-model-rs"),
}

_TO_UTM = Transformer.from_crs("EPSG:4326", "EPSG:25832", always_xy=True)
_TO_WGS = Transformer.from_crs("EPSG:25832", "EPSG:4326", always_xy=True)


def _in_hamburg(lon: float, lat: float) -> bool:
    return HAMBURG_LON[0] <= lon <= HAMBURG_LON[1] and HAMBURG_LAT[0] <= lat <= HAMBURG_LAT[1]


def _centroid_in(
    box: tuple[float, float, float, float], clip: tuple[float, float, float, float]
) -> bool:
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    return clip[0] <= cx <= clip[2] and clip[1] <= cy <= clip[3]


def _sample_utm(
    rng: random.Random,
    extent: tuple[float, float, float, float],
    side_m: float,
    *,
    exclude: tuple[float, float, float, float] | None = None,
    seen: set[tuple[int, int]],
) -> tuple[float, float, float, float]:
    minx, miny, maxx, maxy = extent
    span_x = maxx - minx - side_m
    span_y = maxy - miny - side_m
    for _ in range(400):
        x0 = minx if span_x <= 0 else rng.uniform(minx, minx + max(span_x, 0))
        y0 = miny if span_y <= 0 else rng.uniform(miny, miny + max(span_y, 0))
        box = (x0, y0, x0 + side_m, y0 + side_m)
        key = (round(x0), round(y0))
        if key in seen:
            continue
        if exclude is not None and _centroid_in(box, exclude):
            continue
        seen.add(key)
        return box
    raise RuntimeError(f"could not sample a {side_m / 1000:g} km umring")


def _box_to_wgs(box: tuple[float, float, float, float]) -> dict[str, float] | None:
    min_lon, min_lat = _TO_WGS.transform(box[0], box[1])
    max_lon, max_lat = _TO_WGS.transform(box[2], box[3])
    if not (
        _in_hamburg(min_lon, min_lat)
        and _in_hamburg(max_lon, max_lat)
        and min_lon < max_lon
        and min_lat < max_lat
    ):
        return None
    return {
        "min_x": min_lon,
        "min_y": min_lat,
        "max_x": max_lon,
        "max_y": max_lat,
    }


def random_bbox(
    rng: random.Random, seen: set[tuple[int, int]], side_m: float
) -> tuple[dict[str, float], str]:
    """One square umring; 70 % Innenstadt like example_random_2km.py."""
    km = side_m / 1000.0
    for _ in range(200):
        if rng.random() < CENTER_SHARE:
            box = _sample_utm(rng, CENTER_EPSG, side_m, seen=seen)
            zone = "center"
        else:
            box = _sample_utm(rng, HAMBURG_EPSG, side_m, exclude=CENTER_EPSG, seen=seen)
            zone = "rest"
        bbox = _box_to_wgs(box)
        if bbox is not None:
            return bbox, zone
    raise RuntimeError(f"could not sample a {km:g} km bbox inside Hamburg")


def measure_utm(bbox: dict[str, float]) -> tuple[float, float, float]:
    """Width km, height km, area km² of the WGS84 bbox in EPSG:25832 (SW+NE)."""
    x1, y1 = _TO_UTM.transform(bbox["min_x"], bbox["min_y"])
    x2, y2 = _TO_UTM.transform(bbox["max_x"], bbox["max_y"])
    width_m = abs(x2 - x1)
    height_m = abs(y2 - y1)
    return width_m / 1000.0, height_m / 1000.0, (width_m * height_m) / 1e6


def body_for(bbox: dict[str, float], km: float) -> dict[str, Any]:
    return {
        "inputs": {
            "bbox": bbox,
            "use_dgm_elevation": False,
            "containers": [
                {
                    "containerTitle": "Level of Geometry",
                    "containerId": "level_of_geometry",
                    "components": {
                        "level_of_geom": {"title": "LoD", "value": 1},
                    },
                },
                {
                    "containerTitle": "Projektinformationen",
                    "containerId": "Projektinformationen",
                    "components": {
                        "project": {"title": "Projektname", "value": f"Random {km:g}km"},
                        "site": {"title": "IfcSite", "value": "Hamburg"},
                        "building": {"title": "IfcBuilding", "value": "Test"},
                    },
                },
            ],
        }
    }


def wait_job(
    session: requests.Session,
    base: str,
    job_id: str,
    timeout: float,
) -> tuple[str, dict[str, Any]]:
    deadline = time.monotonic() + timeout
    last: dict[str, Any] = {}
    last_state = ""
    last_beat = 0.0
    while time.monotonic() < deadline:
        try:
            resp = session.get(f"{base}/ogc/jobs/{job_id}", timeout=30)
            resp.raise_for_status()
        except requests.RequestException as exc:
            print(f"  poll retry after {exc.__class__.__name__}", flush=True)
            time.sleep(2)
            continue
        last = resp.json()
        state = str(last.get("status") or "")
        now = time.monotonic()
        if state != last_state or now - last_beat >= 15:
            print(f"  {state or '?'}  {job_id}", flush=True)
            last_state = state
            last_beat = now
        if state in {"successful", "failed", "dismissed"}:
            return state, last
        time.sleep(2)
    return "timeout", last


def _short(text: str, limit: int = 90) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def why_from_job(status: dict[str, Any], state: str, fallback: str = "") -> str:
    """Human reason: empty-umring message or Celery/HTTP failure text."""
    results = status.get("results") or {}
    if isinstance(results, dict) and results.get("message") and not results.get("model"):
        return _short(str(results["message"]))
    raw = status.get("message")
    if isinstance(raw, dict):
        raw = raw.get("error") or raw.get("exc_message") or raw.get("exc_type") or str(raw)
    if raw:
        return _short(str(raw))
    if fallback:
        return _short(fallback)
    if state == "timeout":
        return "job poll timed out"
    if state == "successful":
        return "—"
    return "—"


def ifc_from_job(status: dict[str, Any], output_dir: Path) -> tuple[str, str]:
    """IFC filename and size in MB from a successful job payload."""
    model = (status.get("results") or {}).get("model") or {}
    name = model.get("filename")
    if not name:
        return "—", "—"
    path = output_dir / name
    if not path.is_file():
        return name, "?"
    return name, f"{path.stat().st_size / (1024 * 1024):.2f}"


def _print_one_table(title: str, rows: list[dict[str, Any]]) -> None:
    rows = sorted(rows, key=lambda r: (r["umring"], r["node"]))
    headers = (
        "umring",
        "node",
        "ifc",
        "s",
        "status",
        "mb",
        "width_km",
        "height_km",
        "area_km2",
        "min_x",
        "min_y",
        "max_x",
        "max_y",
    )
    widths = [len(h) for h in headers]
    cells: list[tuple[str, ...]] = []
    for row in rows:
        line = (
            str(row["umring"]),
            str(row["node"]),
            str(row["ifc"]),
            f"{row['seconds']:.1f}",
            str(row["status"]),
            str(row["mb"]),
            f"{row['width_km']:.3f}",
            f"{row['height_km']:.3f}",
            f"{row['area_km2']:.3f}",
            f"{row['bbox']['min_x']:.6f}",
            f"{row['bbox']['min_y']:.6f}",
            f"{row['bbox']['max_x']:.6f}",
            f"{row['bbox']['max_y']:.6f}",
        )
        cells.append(line)
        widths = [max(w, len(c)) for w, c in zip(widths, line)]

    def fmt(parts: tuple[str, ...]) -> str:
        return "  ".join(c.ljust(w) for c, w in zip(parts, widths))

    print()
    print(title)
    print(fmt(headers))
    print("  ".join("-" * w for w in widths))
    for line in cells:
        print(fmt(line))
    times = [r["seconds"] for r in rows]
    mean_s = sum(times) / len(times) if times else 0.0
    print(f"mean time: {mean_s:.1f}s  ({len(rows)} jobs)")


def print_tables(rows: list[dict[str, Any]], output_dir: Path) -> None:
    generic = [r for r in rows if not str(r["node"]).endswith("-rs")]
    rust = [r for r in rows if str(r["node"]).endswith("-rs")]
    if generic:
        _print_one_table("generic", generic)
    if rust:
        _print_one_table("rust", rust)
    print()
    print(f"IFC folder: {output_dir.resolve()}")


def run_job(
    session: requests.Session,
    *,
    base: str,
    node: str,
    bbox: dict[str, float],
    umring: int,
    km: float,
    width_km: float,
    height_km: float,
    area_km2: float,
    timeout: int,
    output_dir: Path,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "umring": umring,
        "node": node,
        "ifc": "—",
        "mb": "—",
        "status": "",
        "why": "—",
        "seconds": 0.0,
        "width_km": width_km,
        "height_km": height_km,
        "area_km2": area_km2,
        "bbox": bbox,
    }
    started = time.monotonic()
    try:
        created = session.post(
            f"{base}/ogc/processes/{node}/execution",
            json=body_for(bbox, km),
            timeout=30,
        )
    except requests.RequestException as exc:
        row["status"] = f"submit-error:{exc.__class__.__name__}"
        row["why"] = _short(str(exc))
        row["seconds"] = time.monotonic() - started
        print(f"  {row['status']}  {row['why']}", flush=True)
        return row
    if not created.ok:
        row["status"] = f"http-{created.status_code}"
        row["why"] = _short(created.text or created.reason)
        row["seconds"] = time.monotonic() - started
        print(f"  {created.status_code} {row['why']}", flush=True)
        return row
    job_id = created.json()["id"]
    print(f"  submitted {job_id}", flush=True)
    state, status = wait_job(session, base, job_id, timeout)
    row["status"] = state
    row["why"] = why_from_job(status, state)
    row["seconds"] = time.monotonic() - started
    row["ifc"], row["mb"] = ifc_from_job(status, output_dir)
    extra = f"  {row['why']}" if row["why"] not in {"—", ""} else ""
    print(f"  {state}  {row['seconds']:.1f}s  {row['ifc']}  {row['mb']} MB{extra}")
    return row


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Random km×km umringe, each run on generic and rust"
    )
    parser.add_argument("--base-url", default="http://localhost:8083")
    parser.add_argument(
        "--kind",
        action="append",
        choices=tuple(KIND_NODES),
        help="tree, city, and/or dgm (repeatable). Default: all three.",
    )
    parser.add_argument(
        "--km",
        type=float,
        default=1.0,
        help="square umring side in kilometres (default: 1)",
    )
    parser.add_argument("--count", type=int, default=20, help="number of umringe")
    parser.add_argument("--timeout", type=int, default=600, help="seconds to wait per job")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).resolve().parent.parent / "output"),
        help="API OUTPUT_FOLDER_PATH (for IFC size on disk)",
    )
    args = parser.parse_args()
    if args.count < 1:
        raise SystemExit("--count must be >= 1")
    if args.km <= 0:
        raise SystemExit("--km must be > 0")

    kinds = args.kind or list(KIND_NODES)
    nodes: list[str] = []
    for kind in kinds:
        nodes.extend(KIND_NODES[kind])
    n_jobs = args.count * len(nodes)
    side_m = args.km * 1000.0
    print(
        f"{args.count} umringe × {args.km:g} km × {len(nodes)} nodes = {n_jobs} jobs  "
        f"kinds={','.join(kinds)}"
    )

    base = args.base_url.rstrip("/")
    output_dir = Path(args.output_dir)
    rng = random.Random(args.seed)
    session = requests.Session()
    session.trust_env = False
    session.mount(
        "http://",
        HTTPAdapter(
            max_retries=Retry(total=5, backoff_factor=0.4, allowed_methods=frozenset(["GET", "POST"]))
        ),
    )

    boxes: list[dict[str, float]] = []
    seen: set[tuple[int, int]] = set()
    for _ in range(args.count):
        bbox, _zone = random_bbox(rng, seen, side_m)
        boxes.append(bbox)

    rows: list[dict[str, Any]] = []
    job_i = 0
    for umring, bbox in enumerate(boxes, start=1):
        width_km, height_km, area_km2 = measure_utm(bbox)
        for node in nodes:
            job_i += 1
            print(
                f"[{job_i}/{n_jobs}] umring {umring}  POST {node}  {area_km2:.3f} km²",
                flush=True,
            )
            rows.append(
                run_job(
                    session,
                    base=base,
                    node=node,
                    bbox=bbox,
                    umring=umring,
                    km=args.km,
                    width_km=width_km,
                    height_km=height_km,
                    area_km2=area_km2,
                    timeout=args.timeout,
                    output_dir=output_dir,
                )
            )

    print_tables(rows, output_dir)


if __name__ == "__main__":
    main()
