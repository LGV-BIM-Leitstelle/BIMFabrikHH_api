"""
Process definitions for OGC API processes.

PROCESS_SPECS is the single place where a process id, title and description are
declared. Both the process list endpoint and the process description endpoint
derive from it, so a new process needs one entry here plus its Celery task in
main_ogc.
"""

from typing import Any, Dict, NamedTuple, Tuple

from BIMFabrikHH_core.data_models.params_tree import RequestParams

PROCESS_VERSION = "0.1.0"


class ProcessSpec(NamedTuple):
    """Metadata of one OGC process. The Celery task is wired up in main_ogc."""

    id: str
    title: str
    description: str


PROCESS_SPECS: Tuple[ProcessSpec, ...] = (
    ProcessSpec(
        "generate-tree-model",
        "Generate BIM tree models as IFC",
        "Creates BIM models of trees within a given bounding box and exports them as an IFC file. "
        "Set use_dgm_elevation=true to assign ground elevation from DGM GeoTIFF tiles (off by default).",
    ),
    ProcessSpec(
        "generate-city-model",
        "Generate BIM city models as IFC",
        "Creates BIM models of city buildings within a bounding box and exports them as an IFC file",
    ),
    ProcessSpec(
        "generate-dgm-model",
        "Generate BIM terrain models as IFC",
        "Creates BIM terrain models within a given bounding box and exports them as an IFC file",
    ),
    ProcessSpec(
        "generate-tree-model-rs",
        "Generate BIM tree models as IFC (Rust)",
        "Creates BIM models of trees within a given bounding box and exports them as an IFC file "
        "via TreesRustApp. Set use_dgm_elevation=true to assign ground elevation from DGM GeoTIFF "
        "tiles (off by default).",
    ),
    ProcessSpec(
        "generate-city-model-rs",
        "Generate BIM city models as IFC (Rust)",
        "Creates BIM models of city buildings within a bounding box and exports them as an IFC file "
        "via CityRustApp (mesh). LoD3 uses DATA_LOD3_FOLDER.",
    ),
    ProcessSpec(
        "generate-dgm-model-rs",
        "Generate BIM terrain models as IFC (Rust)",
        "Creates BIM terrain models within a given bounding box and exports them as an IFC file "
        "via TerrainRustApp (Python mesh, Rust STEP write).",
    ),
)


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
        "version": PROCESS_VERSION,
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


# Full description per process ID, served by /processes/{processID}.
PROCESS_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    spec.id: create_ifc_process_definition(spec.id, spec.title, spec.description)
    for spec in PROCESS_SPECS
}
