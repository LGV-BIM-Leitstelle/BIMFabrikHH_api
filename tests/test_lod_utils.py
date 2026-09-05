"""Unit tests for LoD tile-name resolution (src.api.ogc_api.utils.lod_utils).

The LoD3 cases guard the fix for CityGRID update packages: Hamburg ships some
1 km cells both as a plain ``NNNN.gml`` and as suffixed delivery files
(``NNNN_LoD3-HH_Area4_2024_10_10.gml``) whose extent bleeds across the cell.
A cell the umring touches must pull in every matching file locally, or the
buildings modelled only in an update file are silently dropped.
"""

import pytest

from src.api.ogc_api.utils.lod_utils import transform_file_names_for_lod

pytestmark = [pytest.mark.unit, pytest.mark.city]

# The two LoD1 DK5 cells the sample umring touches (-> CityGRID 6434 / 6435).
UMRING_CELLS = ["LoD1_32_564_5934_1_HH.xml", "LoD1_32_564_5935_1_HH.xml"]


class TestLoD1LoD2Unchanged:
    def test_lod1_passthrough(self):
        assert transform_file_names_for_lod(UMRING_CELLS, 1, None) == UMRING_CELLS

    def test_lod2_prefix_swap(self, tmp_path):
        # Files present so extension resolution keeps the given names.
        for cell in ("LoD2_32_564_5934_1_HH", "LoD2_32_564_5935_1_HH"):
            (tmp_path / f"{cell}.xml").write_text("x")
        out = transform_file_names_for_lod(UMRING_CELLS, 2, str(tmp_path))
        assert out == [
            "LoD2_32_564_5934_1_HH.xml",
            "LoD2_32_564_5935_1_HH.xml",
        ]


class TestLoD3Local:
    def _folder(self, tmp_path, names):
        for name in names:
            (tmp_path / name).write_text("x")
        return str(tmp_path)

    def test_expands_cell_to_plain_and_update_files(self, tmp_path):
        """A touched cell pulls in the plain file *and* its update package."""
        folder = self._folder(
            tmp_path,
            [
                "6434.gml",
                "6434_LoD3-HH_Area4_2024_10_10.gml",
                "6435.gml",
            ],
        )
        out = transform_file_names_for_lod(UMRING_CELLS, 3, folder)
        assert out == [
            "6434.gml",
            "6434_LoD3-HH_Area4_2024_10_10.gml",
            "6435.gml",
        ]

    def test_ignores_update_files_of_untouched_cells(self, tmp_path):
        """Only files for the touched cells are returned, not neighbours."""
        folder = self._folder(
            tmp_path,
            [
                "6434.gml",
                "6435.gml",
                "6335_LoD3-HH_Area4_2024_10_10.gml",  # neighbour, untouched
                "64350.gml",  # different cell, must not prefix-match 6435
            ],
        )
        out = transform_file_names_for_lod(UMRING_CELLS, 3, folder)
        assert out == ["6434.gml", "6435.gml"]

    def test_resolves_xml_extension(self, tmp_path):
        folder = self._folder(tmp_path, ["6434.xml", "6435.gml"])
        out = transform_file_names_for_lod(UMRING_CELLS, 3, folder)
        assert out == ["6434.xml", "6435.gml"]

    def test_missing_cell_falls_back_to_plain_name(self, tmp_path):
        """No file on disk for a cell -> the plain NNNN.gml not-found signal."""
        folder = self._folder(tmp_path, ["6435.gml"])
        out = transform_file_names_for_lod(UMRING_CELLS, 3, folder)
        assert out == ["6434.gml", "6435.gml"]


class TestLoD3Remote:
    def test_remote_falls_back_to_plain_names(self):
        """A remote folder cannot be listed, so only plain names are emitted."""
        out = transform_file_names_for_lod(
            UMRING_CELLS, 3, "https://daten-hamburg.de/BIM/Stadtmodell_LoD3"
        )
        assert out == ["6434.gml", "6435.gml"]

    def test_none_folder_falls_back_to_plain_names(self):
        out = transform_file_names_for_lod(UMRING_CELLS, 3, None)
        assert out == ["6434.gml", "6435.gml"]
