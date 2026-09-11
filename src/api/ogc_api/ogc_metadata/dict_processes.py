"""
Process list configuration for OGC API.

This module contains the process list response structure
for the OGC API - Processes endpoint. Entries are derived from
PROCESS_SPECS so titles and descriptions are declared only once.
"""

from typing import Any, Dict

from .process_definitions import PROCESS_SPECS, PROCESS_VERSION

content_get_processes: Dict[str, Any] = {
    "processes": [
        {
            "id": spec.id,
            "title": spec.title,
            "description": spec.description,
            "version": PROCESS_VERSION,
            "links": [],
        }
        for spec in PROCESS_SPECS
    ]
}
