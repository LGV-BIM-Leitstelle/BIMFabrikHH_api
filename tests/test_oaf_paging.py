"""
Tests for next-link paging of OGC API Features collections.

``HamburgOGCAPI.fetch_all_features`` is what keeps a Flurstueck request from
being silently truncated at one page, so the paging itself is covered here with
a stubbed transport instead of the live API.
"""

from typing import Any, Dict, List, Optional
from unittest.mock import patch

import pytest

from src.api.ogc_api.services.http_requests import HamburgOGCAPI

pytestmark = [pytest.mark.unit]

URL = "https://example.invalid/collections/Flurstueck/items"


def _page(
    features: List[Dict[str, Any]], next_url: Optional[str] = None
) -> Dict[str, Any]:
    """Feature collection page, with a ``rel="next"`` link when given."""
    links = [{"rel": "self", "href": URL}]
    if next_url:
        links.append({"rel": "next", "href": next_url})
    return {
        "type": "FeatureCollection",
        "features": features,
        "numberMatched": 5,
        "numberReturned": len(features),
        "links": links,
    }


def _features(start: int, count: int) -> List[Dict[str, Any]]:
    return [{"id": i} for i in range(start, start + count)]


class TestFetchAllFeatures:
    """Paging behaviour of HamburgOGCAPI.fetch_all_features."""

    def test_single_page_is_returned_unchanged(self):
        with patch.object(HamburgOGCAPI, "fetch_data") as mock_fetch:
            mock_fetch.return_value = _page(_features(0, 3))

            data = HamburgOGCAPI.fetch_all_features(URL, {"limit": 10})

            assert mock_fetch.call_count == 1
            assert len(data["features"]) == 3
            assert data["numberReturned"] == 3

    def test_following_pages_are_appended(self):
        with patch.object(HamburgOGCAPI, "fetch_data") as mock_fetch:
            mock_fetch.side_effect = [
                _page(_features(0, 2), next_url=f"{URL}?offset=2"),
                _page(_features(2, 2), next_url=f"{URL}?offset=4"),
                _page(_features(4, 1)),
            ]

            data = HamburgOGCAPI.fetch_all_features(URL, {"limit": 2})

            assert mock_fetch.call_count == 3
            assert [f["id"] for f in data["features"]] == [0, 1, 2, 3, 4]
            assert data["numberReturned"] == 5

    def test_next_link_is_requested_verbatim(self):
        """The next href already carries limit/offset/bbox/crs."""
        with patch.object(HamburgOGCAPI, "fetch_data") as mock_fetch:
            next_url = f"{URL}?limit=2&offset=2&crs=EPSG"
            mock_fetch.side_effect = [
                _page(_features(0, 2), next_url=next_url),
                _page(_features(2, 1)),
            ]

            HamburgOGCAPI.fetch_all_features(URL, {"limit": 2})

            assert mock_fetch.call_args_list[1].args == (next_url, {})

    def test_empty_page_stops_paging(self):
        """A next link that yields nothing ends the loop instead of looping."""
        with patch.object(HamburgOGCAPI, "fetch_data") as mock_fetch:
            mock_fetch.side_effect = [
                _page(_features(0, 2), next_url=f"{URL}?offset=2"),
                _page([], next_url=f"{URL}?offset=4"),
            ]

            data = HamburgOGCAPI.fetch_all_features(URL, {"limit": 2})

            assert mock_fetch.call_count == 2
            assert len(data["features"]) == 2

    def test_paging_is_bounded(self):
        """A server always offering a next link cannot spin forever."""
        with patch.object(HamburgOGCAPI, "fetch_data") as mock_fetch:
            mock_fetch.return_value = _page(_features(0, 1), next_url=f"{URL}?offset=1")

            data = HamburgOGCAPI.fetch_all_features(URL, {"limit": 1})

            assert mock_fetch.call_count == HamburgOGCAPI.MAX_PAGES + 1
            assert len(data["features"]) == HamburgOGCAPI.MAX_PAGES + 1
