"""
LoD utility functions for OGC API.

This module provides utility functions for handling Level of Detail (LoD)
file name transformations specific to Hamburg's CityGML data.
"""

from typing import List


def transform_file_names_for_lod(tile_names: List[str], lod_level: int) -> List[str]:
    """
    Transform file names to match the LoD level being used.

    This function handles the case where the API returns LoD1 file names
    but the actual files are stored with LoD2 names in LoD2 directories.

    Args:
        tile_names: List of tile file names (e.g., ['LoD1_32_567_5934_1_HH.xml'])
        lod_level: The target LoD level (1 or 2)

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
        return transformed_names
    else:
        # No transformation needed for LoD1 or other levels
        return tile_names

