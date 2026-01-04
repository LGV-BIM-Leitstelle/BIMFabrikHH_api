"""
Conformance configuration for OGC API.

This module contains the conformance response structure
for the OGC API - Processes endpoint.
"""

from typing import Any, Dict

content_conformance: Dict[str, Any] = {
    "conformsTo": [
        "http://www.opengis.net/spec/ogcapi-processes/1.0/conf/core",
        "http://www.opengis.net/spec/ogcapi-processes/1.0/conf/json",
        "http://www.opengis.net/spec/ogcapi-processes/1.0/conf/html",
    ]
}
