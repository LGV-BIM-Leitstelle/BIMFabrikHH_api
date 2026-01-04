"""
Process list configuration for OGC API.

This module contains the process list response structure
for the OGC API - Processes endpoint.
"""

from typing import Any, Dict

content_get_processes: Dict[str, Any] = {
    "processes": [
        {
            "id": "generate-tree-model",
            "title": "Generate 3D tree models as IFC",
            "description": "Creates 3D models of trees within a given bounding box as IFC file",
            "version": "0.1.0",
            "links": [],
        },
        {
            "id": "generate-city-model",
            "title": "Generate 3D city models as IFC",
            "description": "Creates 3D city models from CityGML data within a given bounding box as IFC file",
            "version": "0.1.0",
            "links": [],
        },
        {
            "id": "generate-dgm-model",
            "title": "Generate Digital terrain Models as IFC",
            "description": "Creates 3D terrain models from GeoTIFF data within a given bounding box as IFC file",
            "version": "0.1.0",
            "links": [],
        },
    ]
}
