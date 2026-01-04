"""
Process definitions for OGC API processes.

This module defines the process schemas and metadata for the OGC API
processes including tree model, city model, and DGM model generation.
"""

from typing import Any, Dict

from BIMFabrikHH_core.data_models.params_tree import RequestParams


def create_ifc_process_definition(
    process_id: str, title: str, description: str
) -> Dict[str, Any]:
    """
    Create a standardized IFC process definition.

    Args:
        process_id: Unique identifier for the process.
        title: Human-readable title for the process.
        description: Detailed description of what the process does.

    Returns:
        Dictionary containing the complete process definition.
    """
    return {
        "id": process_id,
        "title": title,
        "description": description,
        "version": "0.1.0",
        "inputs": RequestParams.model_json_schema(),
        "outputs": {
            "ifc_file": {
                "title": "IFC File Links",
                "description": "HTTP and HTTPS links to the generated IFC file",
                "schema": {
                    "type": "object",
                    "properties": {
                        "url-http": {"type": "string", "format": "uri"},
                        "url-https": {"type": "string", "format": "uri"},
                    },
                    "required": ["url-http", "url-https"],
                },
            }
        },
        "links": [],
    }


content_get_process_generate_tree_model = create_ifc_process_definition(
    "generate-tree-model",
    "Generate BIM tree models as IFC",
    "Creates BIM models of trees within a given bounding box and exports them as an IFC file",
)

content_get_process_generate_city_model = create_ifc_process_definition(
    "generate-city-model",
    "Generate BIM city models as IFC",
    "Creates BIM models of city buildings within a bounding box and exports them as an IFC file",
)

content_get_process_generate_dgm_model = create_ifc_process_definition(
    "generate-dgm-model",
    "Generate BIM terrain models as IFC",
    "Creates BIM terrain models within a given bounding box and exports them as an IFC file",
)
