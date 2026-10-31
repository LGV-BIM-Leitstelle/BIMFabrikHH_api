"""
A Nullpunkt outside the CRS of the IFC fails every process with the UI message.

Core rejects the point while the task builds its request parameters, before any
data is fetched, so no external API is needed.
"""

import pytest

from src.api.ogc_api.routes.main_ogc import PROCESS_TASKS
from src.api.ogc_api.utils.user_messages import BASEPOINT_OUTSIDE_CRS_MESSAGE

pytestmark = [pytest.mark.integration, pytest.mark.celery]

BBOX = {"min_x": 9.9756, "min_y": 53.5522, "max_x": 9.9789, "max_y": 53.5536}


@pytest.fixture(autouse=True)
def _enable_eager(celery_eager_mode):
    """Run all tasks in this module eagerly (no worker/broker required)."""
    yield


@pytest.mark.parametrize("process_id", sorted(PROCESS_TASKS))
def test_swapped_nullpunkt_asks_to_check_the_coordinates(
    process_id, assert_task_failed
):
    assert_task_failed(
        PROCESS_TASKS[process_id],
        {"bbox": BBOX, "basepoint": {"x": 5933559.0, "y": 565012.0}},
        match=BASEPOINT_OUTSIDE_CRS_MESSAGE,
        exc_type="ValueError",
    )
