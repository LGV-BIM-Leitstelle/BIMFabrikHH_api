"""
LoD utility functions for OGC API.

Hamburg CityGML tile names and local folder resolution for LoD1–3.
"""

import os
import re
from pathlib import Path
from typing import List, Optional

from BIMFabrikHH_core.config.paths import existing_local_dir

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


def local_city_folder(folder_url: str) -> str:
    """``DATA_BASE_URL`` / LoD folder, as Windows or WSL path."""
    found = existing_local_dir(folder_url)
    if found is not None:
        return str(found)
    if Path(folder_url).is_dir():
        return folder_url
    return folder_url


def gml_paths_for_rust(names: List[str], folder: str) -> List[str]:
    return [name if Path(name).is_file() else str(Path(folder) / name) for name in names]


def _lod3_citygrid_name(lod1_name: str) -> str:
    """``LoD1_32_566_5927_1_HH.xml`` → CityGRID ``6627.gml`` (1 km cell)."""
    match = _LOD1_TILE.match(lod1_name)
    if match is None:
        return lod1_name
    east_km, north_km = int(match.group(1)), int(match.group(2))
    return f"{east_km - 500:02d}{north_km - 5900:02d}.gml"


def transform_file_names_for_lod(
    tile_names: List[str],
    lod_level: int,
    folder_path: Optional[str] = None,
) -> List[str]:
    """
    Transform file names to match the LoD level being used.

    Tile fetch always returns LoD1 DK5 names. LoD2 keeps that pattern with a
    prefix swap. LoD3 CityGRID tiles are ``{east-500}{north-5900}.gml``.

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
    elif lod_level == 3:
        transformed_names = [_lod3_citygrid_name(name) for name in tile_names]
    else:
        transformed_names = list(tile_names)

    return _resolve_tile_extensions(transformed_names, folder_path)


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
