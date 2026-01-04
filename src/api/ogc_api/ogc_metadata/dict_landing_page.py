"""
Landing page configuration for OGC API.

This module contains the landing page response structure
for the OGC API - Processes endpoint.
"""

from typing import Any, Dict

content_landing_page: Dict[str, Any] = {
    "title": "OGC API",
    "description": "OGC API for Processing",
    "links": [
        {
            "href": "/",
            "rel": "self",
            "type": "application/json",
            "title": "This document",
        },
        {
            "href": "/conformance",
            "rel": "conformance",
            "type": "application/json",
            "title": "Conformance declaration",
        },
        {
            "href": "/processes",
            "rel": "processes",
            "type": "application/json",
            "title": "Processes",
        },
        {"href": "/jobs", "rel": "jobs", "type": "application/json", "title": "Jobs"},
    ],
}
