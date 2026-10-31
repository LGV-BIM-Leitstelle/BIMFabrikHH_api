"""
Tests for the Mastermodell (IFC with only the Nullpunktobjekt).

Tasks run in Celery eager mode (see the ``celery_eager_mode`` fixture in
conftest.py). The core app needs no external data, so it runs for real.
"""

from unittest.mock import patch

import ifcopenshell
import ifcopenshell.util.element
import ifcopenshell.util.placement
import pytest

from src.api.ogc_api.services.generate_bim_modells import (
    execute_generate_basepoint_model,
)
from src.api.ogc_api.utils.user_messages import (
    BASEPOINT_IFC_FAILED_MESSAGE,
    BASEPOINT_MISSING_MESSAGE,
)

pytestmark = [pytest.mark.integration, pytest.mark.celery]

BBOX = {"min_x": 9.9756, "min_y": 53.5522, "max_x": 9.9789, "max_y": 53.5536}


@pytest.fixture(autouse=True)
def _enable_eager(celery_eager_mode):
    """Run all tasks in this module eagerly (no worker/broker required)."""
    yield


@pytest.fixture
def output_folder(tmp_path):
    with patch("src.api.ogc_api.services.generate_bim_modells.OUTPUT_FOLDER", tmp_path):
        yield tmp_path


def _nullpunkt(path):
    model = ifcopenshell.open(str(path))
    (proxy,) = model.by_type("IfcBuildingElementProxy")
    xyz = ifcopenshell.util.placement.get_local_placement(proxy.ObjectPlacement)[:3, 3]
    return proxy, tuple(float(v) for v in xyz)


def test_mastermodell_has_the_entered_nullpunkt(output_folder):
    result = execute_generate_basepoint_model.delay(
        {"bbox": BBOX, "basepoint": {"x": 565012.25, "y": 5933559.5, "z": 12.5}}
    ).get(timeout=30)

    filename = result["model"]["filename"]
    assert filename.startswith("Mastermodell_")
    proxy, xyz = _nullpunkt(output_folder / filename)
    assert proxy.Name == "Nullpunktobjekt"
    assert xyz == pytest.approx((565012.25, 5933559.5, 12.5))
    psets = ifcopenshell.util.element.get_psets(proxy)
    assert psets["Pset_Objektinformation"]["_IDEbene1"] == "Nullpunktobjekt"


def test_mastermodell_needs_no_umring_when_the_nullpunkt_is_entered(output_folder):
    result = execute_generate_basepoint_model.delay(
        {"basepoint": {"x": 565012.25, "y": 5933559.5}}
    ).get(timeout=30)

    _, xyz = _nullpunkt(output_folder / result["model"]["filename"])
    assert xyz == pytest.approx((565012.25, 5933559.5, 0.0))


def test_mastermodell_without_umring_and_nullpunkt_asks_for_the_nullpunkt(
    output_folder, assert_task_failed
):
    assert_task_failed(
        execute_generate_basepoint_model,
        {},
        match=BASEPOINT_MISSING_MESSAGE,
        exc_type="ValueError",
    )


def test_mastermodell_without_entry_uses_the_lower_left_of_the_umring(output_folder):
    result = execute_generate_basepoint_model.delay({"bbox": BBOX}).get(timeout=30)

    _, (x, y, z) = _nullpunkt(output_folder / result["model"]["filename"])
    assert 560000 < x < 570000 and 5930000 < y < 5940000
    assert z == 0.0


def test_mastermodell_reports_a_failed_write(output_folder, assert_task_failed):
    with patch(
        "src.api.ogc_api.services.generate_bim_modells.BasepointGenericApp.build_ifc",
        return_value=None,
    ):
        assert_task_failed(
            execute_generate_basepoint_model,
            {"bbox": BBOX},
            match=BASEPOINT_IFC_FAILED_MESSAGE,
            exc_type="ValueError",
        )
