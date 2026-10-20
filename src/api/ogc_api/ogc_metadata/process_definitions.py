"""
Process definitions for OGC API processes.

PROCESS_SPECS is the single place where a process id, title and description are
declared. Both the process list endpoint and the process description endpoint
derive from it, so a new process needs one entry here plus its Celery task in
main_ogc.
"""

from typing import Any, Dict, NamedTuple, Optional, Tuple

from BIMFabrikHH_core.data_models.params_tree import RequestParams

PROCESS_VERSION = "0.1.0"

# Well-known container/component identifiers used to pass "level_of_geom"
# (Detailierungsgrad / LoD) in a process execution request. Must stay in
# sync with BIMFabrikHH_core's ogc_extractor.json
# (LEVEL_OF_GEOMETRY_CONTAINER_ID / LEVEL_OF_GEOMETRY_COMPONENT_KEY).
LEVEL_OF_GEOMETRY_CONTAINER_ID = "level_of_geometry"
LEVEL_OF_GEOMETRY_COMPONENT_KEY = "level_of_geom"


class ProcessSpec(NamedTuple):
    """Metadata of one OGC process. The Celery task is wired up in main_ogc."""

    id: str
    title: str
    description: str


class LodSpec(NamedTuple):
    """Valid ``level_of_geom`` range for one process, plus per-value meaning.

    Sourced from the Celery task bodies in ``services/generate_bim_modells.py``:
    Each ``value_titles`` entry documents what that specific
    integer does for this process.
    """

    values: Tuple[int, ...]
    value_titles: Dict[int, str]
    summary: str


# Per-process level_of_geom (Detailierungsgrad) support. ``None`` means the
# process does not read level_of_geom at all (no extract_level_of_geometry
# call in its Celery task).
LOD_SPECS: Dict[str, Optional[LodSpec]] = {
    "generate-tree-model": LodSpec(
        values=(1, 2, 3, 4),
        value_titles={
            1: "Lowest crown mesh detail (icosphere subdivision level 1)",
            2: "Crown mesh detail level 2",
            3: "Crown mesh detail level 3",
            4: "Highest crown mesh detail (icosphere subdivision level 4)",
        },
        summary="Crown geometry detail level; also written to the IFC _LoG property (100-400).",
    ),
    "generate-tree-model-rs": LodSpec(
        values=(1, 2, 3, 4),
        value_titles={
            1: "Lowest crown mesh detail (icosphere subdivision level 1)",
            2: "Crown mesh detail level 2",
            3: "Crown mesh detail level 3",
            4: "Highest crown mesh detail (icosphere subdivision level 4)",
        },
        summary="Crown geometry detail level; also written to the IFC _LoG property (100-400).",
    ),
    "generate-city-model": LodSpec(
        values=(1, 2),
        value_titles={
            1: "LoD1 block massing",
            2: "LoD2 detailed roofs",
        },
        summary="CityGML level of detail. LoD3 is not available on this process; use generate-city-model-rs.",
    ),
    "generate-city-model-rs": LodSpec(
        values=(1, 2, 3),
        value_titles={
            1: "LoD1 block massing",
            2: "LoD2 detailed roofs",
            3: "LoD3 detailed facades",
        },
        summary="CityGML level of detail.",
    ),
    "generate-dgm-model": LodSpec(
        values=(1, 2),
        value_titles={
            1: "Single terrain mesh (default)",
            2: "Terrain split by ALKIS Nutzung parcels",
        },
        summary="Terrain (DGM) generation mode.",
    ),
    "generate-dgm-model-rs": LodSpec(
        values=(1, 2),
        value_titles={
            1: "Single terrain mesh (default)",
            2: "Terrain split by ALKIS Nutzung parcels",
        },
        summary="Terrain (DGM) generation mode.",
    ),
    "generate-flurstuecke-model": None,
    "generate-boreholes-model": None,
}


PROCESS_SPECS: Tuple[ProcessSpec, ...] = (
    ProcessSpec(
        "generate-tree-model",
        "Generate BIM tree models as IFC",
        "Creates BIM models of trees within a given bounding box and exports them as an IFC file. "
        "Trees are draped onto DGM GeoTIFF tiles by default; set use_dgm_elevation=false to keep Z at 0.",
    ),
    ProcessSpec(
        "generate-city-model",
        "Generate BIM city models as IFC",
        "Creates BIM models of city buildings within a bounding box and exports them as an IFC file",
    ),
    ProcessSpec(
        "generate-dgm-model",
        "Generate BIM terrain models as IFC",
        "Creates BIM terrain models within a given bounding box and exports them as an IFC file. "
        "level_of_geom=1 (default) is a single DGM; level_of_geom=2 splits by ALKIS Nutzung parcels.",
    ),
    ProcessSpec(
        "generate-flurstuecke-model",
        "Generate BIM cadastral parcel models as IFC",
        "Creates BIM models of ALKIS Flurstücke within a given bounding box and exports them as an "
        "IFC file. Each parcel footprint becomes an IfcBuildingElementProxy extruded 30 m from z=0, "
        "coloured per Gemarkung.",
    ),
    ProcessSpec(
        "generate-boreholes-model",
        "Generate BIM borehole models as IFC",
        "Creates BIM models of Hamburg Baugrundaufschlüsse (BoreholeML 3.0 WFS) within a given "
        "bounding box and exports them as an IFC file. Each soil layer becomes an "
        "IfcBuildingElementProxy cylinder stacked from the Ansatzpunkt, coloured per DIN 4023. "
        "The umring is limited to 0.1 km².",
    ),
    ProcessSpec(
        "generate-tree-model-rs",
        "Generate BIM tree models as IFC (Rust)",
        "Creates BIM models of trees within a given bounding box and exports them as an IFC file "
        "via TreesRustApp. Trees are draped onto DGM GeoTIFF tiles by default; set "
        "use_dgm_elevation=false to keep Z at 0.",
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
        "via TerrainRustApp (Python mesh, Rust STEP write). "
        "level_of_geom=1 (default) is a single DGM; level_of_geom=2 splits by ALKIS Nutzung parcels.",
    ),
)


def _level_of_geometry_container_schema(lod_spec: LodSpec) -> Dict[str, Any]:
    """JSON Schema branch for the well-known ``level_of_geometry`` container.

    Constrains ``containerId`` to the fixed value and the ``level_of_geom``
    component's ``value`` to the process-specific enum, without touching the
    generic ``Container``/``Component`` schema used by any other container.
    """
    value_lines = "; ".join(
        f"{value}={title}" for value, title in lod_spec.value_titles.items()
    )
    return {
        "type": "object",
        "required": ["containerId", "components"],
        "properties": {
            "containerId": {"const": LEVEL_OF_GEOMETRY_CONTAINER_ID},
            "components": {
                "type": "object",
                "required": [LEVEL_OF_GEOMETRY_COMPONENT_KEY],
                "properties": {
                    LEVEL_OF_GEOMETRY_COMPONENT_KEY: {
                        "type": "object",
                        "properties": {
                            "value": {
                                "type": "integer",
                                "enum": list(lod_spec.values),
                                "description": f"{lod_spec.summary} Allowed values: {value_lines}.",
                            }
                        },
                    }
                },
            },
        },
    }


def _containers_input_description(
    process_id: str, defs: Dict[str, Any]
) -> Dict[str, Any]:
    """Build the ``containers`` OGC ``InputDescription`` entry for one process.

    ``containers`` carries generic ``{containerId, components}`` extension
    data (project info, property sets, ...); when the process also reads
    ``level_of_geom`` (Detailierungsgrad / LoD), a second ``anyOf`` branch
    documents the well-known ``level_of_geometry`` container and hard-enums
    its accepted values for this specific process.
    """
    lod_spec = LOD_SPECS.get(process_id)
    any_of = [{"$ref": "#/$defs/Container"}]
    description = (
        "Optional list of extension containers, each carrying a set of named "
        "components ({containerId, components: {key: {title, value}}}). Used "
        "to pass metadata (e.g. project info, property sets) alongside bbox."
    )
    examples = [
        [
            {
                "containerId": "tree_data",
                "containerTitle": "Tree Information",
                "components": {"species": {"title": "Tree Species", "value": "Oak"}},
            }
        ]
    ]

    if lod_spec is not None:
        any_of.append(_level_of_geometry_container_schema(lod_spec))
        value_lines = "; ".join(
            f"{value}={title}" for value, title in lod_spec.value_titles.items()
        )
        description += (
            f" To select the level of detail (Detailierungsgrad), include a container with "
            f"containerId='{LEVEL_OF_GEOMETRY_CONTAINER_ID}' and a component "
            f"'{LEVEL_OF_GEOMETRY_COMPONENT_KEY}' whose value is one of "
            f"{list(lod_spec.values)}. {lod_spec.summary} Allowed values: {value_lines}."
        )
        examples.append(
            [
                {
                    "containerId": LEVEL_OF_GEOMETRY_CONTAINER_ID,
                    "components": {
                        LEVEL_OF_GEOMETRY_COMPONENT_KEY: {
                            "title": "Level Of Geometry",
                            "value": lod_spec.values[0],
                        }
                    },
                }
            ]
        )
    else:
        description += (
            " This process does not read level_of_geom (no level of detail selection)."
        )

    return {
        "title": "OGC containers (extension components)",
        "description": description,
        "minOccurs": 0,
        "maxOccurs": 1,
        "schema": {
            "type": "array",
            "items": {"anyOf": any_of},
            "$defs": {"Container": defs["Container"], "Component": defs["Component"]},
            "examples": examples,
        },
    }


def create_ifc_process_definition(
    process_id: str, title: str, description: str
) -> Dict[str, Any]:
    """
    Create a standardized IFC process definition.

    Builds ``inputs`` as an OGC API - Processes Part 1 conformant map of
    ``input-id -> InputDescription`` (title, description, schema, minOccurs,
    maxOccurs), instead of dumping the raw ``RequestParams`` model schema.

    Args:
        process_id: Unique identifier for the process.
        title: Human-readable title for the process.
        description: Detailed description of what the process does.

    Returns:
        Dictionary containing the complete process definition.
    """
    schema = RequestParams.model_json_schema()
    defs = schema["$defs"]
    properties = schema["properties"]

    inputs: Dict[str, Any] = {
        "bbox": {
            "title": "Bounding box (WGS84)",
            "description": properties["bbox"]["description"],
            "minOccurs": 0,
            "maxOccurs": 1,
            "schema": {
                "$ref": "#/$defs/BoundingBoxParams",
                "$defs": {"BoundingBoxParams": defs["BoundingBoxParams"]},
            },
        },
        "containers": _containers_input_description(process_id, defs),
        "use_dgm_elevation": {
            "title": "Use DGM elevation",
            "description": properties["use_dgm_elevation"]["description"],
            "minOccurs": 0,
            "maxOccurs": 1,
            "schema": {
                "type": "boolean",
                "default": properties["use_dgm_elevation"]["default"],
            },
        },
    }

    return {
        "id": process_id,
        "title": title,
        "description": description,
        "version": PROCESS_VERSION,
        "inputs": inputs,
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
