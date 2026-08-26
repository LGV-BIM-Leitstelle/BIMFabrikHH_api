"""
LoD utility functions for OGC API.

This module provides utility functions for handling Level of Detail (LoD)
file name transformations specific to Hamburg's CityGML data.
"""

import os
from typing import List, Optional

# Extensions accepted for CityGML tiles, in resolution priority order.
CITYGML_EXTENSIONS = (".gml", ".xml")


def transform_file_names_for_lod(
    tile_names: List[str],
    lod_level: int,
    folder_path: Optional[str] = None,
) -> List[str]:
    """
    Transform file names to match the LoD level being used.

    This function handles the case where the API returns LoD1 file names
    but the actual files are stored with LoD2 names in LoD2 directories.

    Hamburg's tiles are stored with either a ``.xml`` or ``.gml`` extension
    When ``folder_path`` is a local directory, each tile is resolved to whichever
    extension actually exists on disk, so both extensions are accepted for
    both LoD levels.

    Args:
        tile_names: List of tile file names (e.g., ['LoD1_32_567_5934_1_HH.xml'])
        lod_level: The target LoD level (1 or 2)
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
    """
    if lod_level == 2:
        # Transform LoD1 names to LoD2 names
        transformed_names = []
        for name in tile_names:
            if name.startswith("LoD1_"):
                # Replace LoD1 with LoD2 in the filename
                lod2_name = name.replace("LoD1_", "LoD2_")
                transformed_names.append(lod2_name)
            else:
                transformed_names.append(name)
    else:
        # No name transformation needed for LoD1 or other levels
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
