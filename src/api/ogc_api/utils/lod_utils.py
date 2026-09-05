"""
LoD utility functions for OGC API.

Hamburg CityGML tile names and LoD folder lookup for LoD1–3. Turning a
configured folder into one this OS can open is
:func:`BIMFabrikHH_core.config.paths.local_dir_or_raw`.
"""

import glob
import os
import re
from pathlib import Path
from typing import List, Optional

from src.api.config.settings import api_settings

# Extensions accepted for CityGML tiles, in resolution priority order.
CITYGML_EXTENSIONS = (".gml", ".xml")

_LOD1_TILE = re.compile(r"^LoD1_32_(\d+)_(\d+)_", re.IGNORECASE)


def lod_data_folder(lod_level: int) -> str:
    if lod_level == 3:
        return api_settings.DATA_LOD3_FOLDER
    if lod_level == 2:
        return api_settings.DATA_LOD2_FOLDER
    return api_settings.DATA_LOD1_FOLDER


def lod_folder_url(lod_level: int) -> str:
    return f"{api_settings.DATA_BASE_URL}/{lod_data_folder(lod_level)}"


def gml_paths_for_rust(names: List[str], folder: str) -> List[str]:
    return [name if Path(name).is_file() else str(Path(folder) / name) for name in names]


def _lod3_citygrid_stem(lod1_name: str) -> Optional[str]:
    """LoD1 DK5 name → CityGRID 4-digit cell stem, e.g. ``6627``.

    ``LoD1_32_566_5927_1_HH.xml`` → ``6627`` (east−500, north−5900). Returns
    ``None`` when ``lod1_name`` is not a LoD1 DK5 tile name.
    """
    match = _LOD1_TILE.match(lod1_name)
    if match is None:
        return None
    east_km, north_km = int(match.group(1)), int(match.group(2))
    return f"{east_km - 500:02d}{north_km - 5900:02d}"


def _lod3_files_for_stem(stem: str, folder_path: str) -> List[str]:
    """Every CityGRID file for a 1 km cell ``stem`` in a local ``folder_path``.

    Hamburg delivers LoD3 both as plain ``NNNN.gml`` cells and as suffixed
    update packages (``NNNN_LoD3-HH_Area4_2024_10_10.gml``) whose extent bleeds
    across the nominal cell. A cell the umring touches must pull in all of them,
    otherwise buildings modelled only in an update file are silently dropped.
    """
    matches: List[str] = []
    for pattern in (f"{stem}.gml", f"{stem}.xml", f"{stem}_*.gml", f"{stem}_*.xml"):
        for path in glob.glob(os.path.join(folder_path, pattern)):
            matches.append(os.path.basename(path))
    return sorted(set(matches))


def _lod3_tile_names(tile_names: List[str], folder_path: Optional[str]) -> List[str]:
    """Resolve LoD3 CityGRID file names for the cells the umring touches.

    Locally, each touched cell expands to every matching CityGRID file (the
    plain cell plus any suffixed update packages). A remote folder has no
    listing to enumerate, so fall back to the plain ``NNNN.gml`` name.
    """
    is_local = bool(folder_path) and not folder_path.startswith(("http://", "https://"))
    resolved: List[str] = []
    seen: set = set()

    def _add(name: str) -> None:
        if name not in seen:
            seen.add(name)
            resolved.append(name)

    for name in tile_names:
        stem = _lod3_citygrid_stem(name)
        if stem is None:
            _add(name)
            continue
        matches = (
            _lod3_files_for_stem(stem, folder_path)  # type: ignore[arg-type]
            if is_local
            else []
        )
        if matches:
            for match in matches:
                _add(match)
        else:
            _add(f"{stem}.gml")
    return resolved


def transform_file_names_for_lod(
    tile_names: List[str],
    lod_level: int,
    folder_path: Optional[str] = None,
) -> List[str]:
    """
    Transform file names to match the LoD level being used.

    Tile fetch always returns LoD1 DK5 names. LoD2 keeps that pattern with a
    prefix swap. LoD3 CityGRID cells are ``{east-500}{north-5900}`` and, when
    the folder is local, each cell expands to every matching file: the plain
    ``NNNN.gml`` plus any suffixed update packages (see :func:`_lod3_tile_names`).

    Hamburg's tiles are stored with either a ``.xml`` or ``.gml`` extension
    When ``folder_path`` is a local directory, each tile is resolved to whichever
    extension actually exists on disk, so both extensions are accepted for
    both LoD levels.

    Args:
        tile_names: List of tile file names (e.g., ['LoD1_32_567_5934_1_HH.xml'])
        lod_level: The target LoD level (1, 2, or 3)
        folder_path: Optional directory (local path or URL) holding the tiles.
            When a local path is given, the file extension is resolved to the
            file that exists (``.gml`` or ``.xml``).

    Returns:
        List of transformed file names

    Examples:
        >>> transform_file_names_for_lod(['LoD1_32_567_5934_1_HH.xml'], 2)
        ['LoD2_32_567_5934_1_HH.xml']

        >>> transform_file_names_for_lod(['LoD1_32_567_5934_1_HH.xml'], 1)
        ['LoD1_32_567_5934_1_HH.xml']

        >>> transform_file_names_for_lod(['LoD1_32_566_5927_1_HH.xml'], 3)
        ['6627.gml']
    """
    if lod_level == 2:
        transformed_names = []
        for name in tile_names:
            if name.startswith("LoD1_"):
                transformed_names.append(name.replace("LoD1_", "LoD2_"))
            else:
                transformed_names.append(name)
        return _resolve_tile_extensions(transformed_names, folder_path)

    if lod_level == 3:
        return _lod3_tile_names(tile_names, folder_path)

    return _resolve_tile_extensions(list(tile_names), folder_path)


def _resolve_tile_extensions(
    tile_names: List[str], folder_path: Optional[str]
) -> List[str]:
    """
    Resolve each tile file name to an extension that exists in the folder.

    Both ``.gml`` and ``.xml`` are accepted. Remote (http/https) folders and
    names for which no matching file is found are returned unchanged, so the
    caller can surface a proper "not found" error.
    """
    if not folder_path or folder_path.startswith(("http://", "https://")):
        return tile_names

    resolved = []
    for name in tile_names:
        base, _ext = os.path.splitext(name)
        candidate = name
        for ext in CITYGML_EXTENSIONS:
            if os.path.isfile(os.path.join(folder_path, base + ext)):
                candidate = base + ext
                break
        resolved.append(candidate)
    return resolved
