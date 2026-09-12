"""
HTTP request services for external API calls.
Moved from core package to API package to maintain separation of concerns.

Copyright (C) 2025 Freie und Hansestadt Hamburg, Landesbetrieb Geoinformation und Vermessung
BIM-Leitstelle, Ahmed Salem <ahmed.salem@gv.hamburg.de>
"""

import logging
from typing import Any, Dict, List, Optional

import pandas as pd
from lxml import etree
import requests
from BIMFabrikHH_core.core.utils import MathTool

from ...config.settings import api_settings

LOGGER = logging.getLogger(__name__)


class HamburgOGCAPI:
    """Handles HTTP requests to Hamburg OGC APIs."""

    # API settings from configuration
    TIMEOUT = api_settings.API_TIMEOUT
    DEFAULT_LIMIT = api_settings.API_DEFAULT_LIMIT
    DEFAULT_CRS = api_settings.API_DEFAULT_CRS

    # Safety stop for next-link paging (see fetch_all_features).
    MAX_PAGES = 20

    @staticmethod
    def fetch_data(url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fetch data from OGC API with error handling.

        Args:
            url: The API endpoint URL
            params: Query parameters

        Returns:
            API response data as dictionary for JSON responses

        Raises:
            requests.RequestException: If the request fails
        """
        try:
            LOGGER.info(f"Fetching data from: {url}")
            response = requests.get(url, params=params, timeout=HamburgOGCAPI.TIMEOUT)
            response.raise_for_status()

            data = response.json()

            LOGGER.info(f"Successfully fetched data from {url}")
            return data

        except requests.RequestException as e:
            LOGGER.error(f"Failed to fetch data from {url}: {e}")
            raise

    @staticmethod
    def fetch_all_features(url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch one feature collection, following ``rel="next"`` links.

        ldproxy caps a page at the requested ``limit``, so a collection with
        more matches than that is split across pages. Trees fit into a single
        page, but a 1 km² umring can hold thousands of Flurstücke, and a
        truncated page would silently drop parcels from the model.

        Returns the first page with every following page's features appended.
        """
        collection = HamburgOGCAPI.fetch_data(url, params)
        features: List[Dict[str, Any]] = list(collection.get("features") or [])

        # The next link already carries limit/offset/bbox/crs, so it is
        # requested as-is. Bounded so a server that keeps handing out a next
        # link cannot spin forever.
        page = collection
        for _ in range(HamburgOGCAPI.MAX_PAGES):
            next_url = HamburgOGCAPI._next_page_url(page)
            if next_url is None:
                break
            page = HamburgOGCAPI.fetch_data(next_url, {})
            page_features = page.get("features") or []
            if not page_features:
                break
            features.extend(page_features)
        else:
            LOGGER.warning(
                "Stopped paging %s after %d pages (%d features)",
                url,
                HamburgOGCAPI.MAX_PAGES,
                len(features),
            )

        collection["features"] = features
        collection["numberReturned"] = len(features)
        return collection

    @staticmethod
    def _next_page_url(collection: Dict[str, Any]) -> Optional[str]:
        """URL of the ``rel="next"`` link of ``collection``, or ``None``."""
        for link in collection.get("links") or []:
            if link.get("rel") == "next" and link.get("href"):
                return str(link["href"])
        return None

    @staticmethod
    def data_to_dataframe(data: Dict[str, Any]) -> pd.DataFrame:
        """
        Convert API response data to a Pandas DataFrame.

        Args:
            data (dict): API response data containing features.

        Returns:
            pd.DataFrame: DataFrame containing extracted features.
        """
        if not data or "features" not in data:
            LOGGER.warning("No valid data found in response")
            return pd.DataFrame()

        features = [HamburgOGCAPI._extract_feature(f) for f in data["features"]]
        df = pd.DataFrame(features)

        if df.empty:
            LOGGER.warning("No valid features found")

        return df

    @staticmethod
    def _extract_feature(feature: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract relevant data from a single feature.

        Args:
            feature (dict): A single feature from the API response.

        Returns:
            dict: Processed feature data with coordinates and properties.
        """
        geometry = feature.get("geometry", {})
        coords = geometry.get("coordinates", [])
        x, y = (None, None)

        if geometry.get("type") == "Point" and len(coords) == 2:
            x, y = MathTool.float_4f(str(coords[0])), MathTool.float_4f(str(coords[1]))
        elif (
            geometry.get("type") == "MultiPoint"
            and len(coords) > 0
            and len(coords[0]) == 2
        ):
            x, y = MathTool.float_4f(str(coords[0][0])), MathTool.float_4f(
                str(coords[0][1])
            )

        return {
            "id": feature.get("id"),
            "Easting": x,
            "Northing": y,
            **feature.get("properties", {}),
        }

    @staticmethod
    def get_tiles(
        x1: float, y1: float, x2: float, y2: float, model_type: str = "citymodel"
    ) -> List[str]:
        """
        Fetch tile names within a specified bounding box.

        Args:
            x1: Minimum x coordinate of bounding box
            y1: Minimum y coordinate of bounding box
            x2: Maximum x coordinate of bounding box
            y2: Maximum y coordinate of bounding box
            model_type: Type of model ('citymodel' or 'basic')

        Returns:
            List of transformed tile names
        """
        params = {
            "f": "json",
            "bbox": f"{x1},{y1},{x2},{y2}",
            "skipGeometry": "false",
        }

        url = str(api_settings.DGM_TILES_API_URL)
        data = HamburgOGCAPI.fetch_data(url, params)
        df = HamburgOGCAPI.data_to_dataframe(data)

        if df.empty or "kachelbezeichnung_dk5" not in df:
            LOGGER.warning("No tile data found for the specified bounding box")
            return []

        df["kachelbezeichnung_dk5"] = df["kachelbezeichnung_dk5"].apply(
            lambda val: HamburgOGCAPI._transform_value(val, model_type)
        )

        tiles = df["kachelbezeichnung_dk5"].dropna().tolist()
        LOGGER.info(f"Found {len(tiles)} tiles for {model_type}")
        return tiles

    @staticmethod
    def _transform_value(value: str, model_type: str = "citymodel") -> Optional[str]:
        """
        Transform raw tile name into appropriate filename format for a given model type.

        Args:
            value: Raw tile name (e.g., "DK5_565000_5932000").
            model_type: Model type ('citymodel' or 'basic').

        Returns:
            Transformed filename or None if format invalid.
        """
        parts = value.split("_")
        if len(parts) != 3:
            return None

        try:
            x = int(parts[1]) // 1000
            if model_type == "citymodel":
                y = int(parts[2]) // 1000  # 5932000 → 5932
                return f"LoD1_32_{x}_{y}_1_HH.xml"
            elif model_type == "basic":
                y = (int(parts[2]) // 100) % 10000  # 5932000 → 9320
                return f"dgm1_32_{x}_{y}_1_hh_2022.tif"
            else:
                return None

        except ValueError as e:
            LOGGER.warning(
                f"Failed to transform tile value '{value}' for {model_type}: {e}"
            )
            return None


class WFSAPI:
    """Handles HTTP requests to WFS APIs."""

    # API settings from configuration
    TIMEOUT = api_settings.API_TIMEOUT

    @staticmethod
    def fetch_data(url: str, params: Dict[str, Any]) -> etree._Element:
        """
        Fetch data from WFS API with error handling.

        Args:
            url: The API endpoint URL
            params: Query parameters

        Returns:
            API response data as an XML element.

        Raises:
            requests.RequestException: If the request fails
        """

        LOGGER.info("Fetching data from: %s", url)

        try:
            response = requests.get(url, params=params, timeout=WFSAPI.TIMEOUT)
            response.raise_for_status()
            data = etree.fromstring(response.content)

        except requests.RequestException:
            LOGGER.exception("Failed to fetch data from %s:", url)
            raise
        except etree.XMLSyntaxError:
            LOGGER.exception("Invalid XML received from %s", url)
            raise

        LOGGER.info("Successfully fetched data from %s", url)
        return data


class DataFetcher:
    """Handles fetching raw data from various sources."""

    @staticmethod
    def fetch_tree_data(bbox: Dict[str, float]) -> Dict[str, Any]:
        """
        Fetch tree data from OAF API.

        Args:
            bbox: Bounding box parameters

        Returns:
            Raw tree data from API
        """
        params = {
            "f": "json",
            "bbox": f"{bbox['min_x']},{bbox['min_y']},{bbox['max_x']},{bbox['max_y']}",
            "crs": HamburgOGCAPI.DEFAULT_CRS,
            "limit": HamburgOGCAPI.DEFAULT_LIMIT,
            "skipGeometry": "false",
        }

        url = str(api_settings.TREES_API_URL)
        return HamburgOGCAPI.fetch_data(url, params)

    @staticmethod
    def fetch_tree_data_hafen(bbox: Dict[str, float]) -> Dict[str, Any]:
        """
        Fetch harbor tree data from OAF API.

        Args:
            bbox: Bounding box parameters

        Returns:
            Raw harbor tree data from API
        """
        params = {
            "f": "json",
            "bbox": f"{bbox['min_x']},{bbox['min_y']},{bbox['max_x']},{bbox['max_y']}",
            "crs": HamburgOGCAPI.DEFAULT_CRS,
            "limit": HamburgOGCAPI.DEFAULT_LIMIT,
            "skipGeometry": "false",
        }

        url = str(api_settings.TREES_HAFEN_API_URL)
        return HamburgOGCAPI.fetch_data(url, params)

    @staticmethod
    def fetch_citymodel_tiles(bbox: Dict[str, float]) -> List[str]:
        """
        Fetch city model tile information.

        Args:
            bbox: Bounding box parameters

        Returns:
            List of tile file names
        """
        return HamburgOGCAPI.get_tiles(
            bbox["min_x"],
            bbox["min_y"],
            bbox["max_x"],
            bbox["max_y"],
            model_type="citymodel",
        )

    @staticmethod
    def fetch_dgm_tiles(bbox: Dict[str, float]) -> List[str]:
        """
        Fetch DGM tile information.

        Args:
            bbox: Bounding box parameters

        Returns:
            List of tile file names
        """
        return HamburgOGCAPI.get_tiles(
            bbox["min_x"],
            bbox["min_y"],
            bbox["max_x"],
            bbox["max_y"],
            model_type="basic",
        )

    @staticmethod
    def fetch_borehole_data(bbox: Dict[str, float]) -> etree._Element:
        """
        Fetch borehole data from the WFS BoreholeML 3.0 API.

        Args:
            bbox: Bounding box parameters

        Returns:
            Raw borehole data
        """
        params = {
            "bbox": f"{bbox['min_x']},{bbox['min_y']},{bbox['max_x']},{bbox['max_y']},EPSG:4326",
        }

        url = str(api_settings.WFS_BOREHOLE_API_URL)
        return WFSAPI.fetch_data(url, params)
