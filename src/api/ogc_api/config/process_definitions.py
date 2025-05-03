content_get_process_get_trees = {
    "id": "get-trees",
    "title": "Get trees within bounding box",
    "description": "Fetches tree data from Hamburg's open data portal within given bounding box",
    "version": "1.0.0",
    "inputs": {
        "bbox": {
            "title": "Bounding box",
            "description": "Area of interest",
            "schema": {
                "type": "object",
                "properties": {
                    "min_x": {"type": "number"},
                    "min_y": {"type": "number"},
                    "max_x": {"type": "number"},
                    "max_y": {"type": "number"},
                },
                "required": ["min_x", "min_y", "max_x", "max_y"],
            },
            "default": {
                "min_x": 9.9733,
                "min_y": 53.5544,
                "max_x": 9.9756,
                "max_y": 53.5556,
            },
        },
        "crs": {
            "title": "Coordinate Reference System",
            "schema": {"type": "string"},
            "default": "http://www.opengis.net/def/crs/EPSG/0/25832",
        },
        "limit": {
            "title": "Maximum number of trees",
            "schema": {"type": "integer", "minimum": 1, "maximum": 5000},
            "default": 1000,
        },
        "skip_geometry": {
            "title": "Skip geometry data",
            "schema": {"type": "boolean"},
            "default": False,
        },
    },
    "outputs": {
        "trees": {
            "title": "Tree data",
            "description": "GeoJSON data of trees",
            "schema": {"type": "object"},
        }
    },
    "links": [],
}

content_get_process_generate_tree_model = {
    "id": "generate-tree-model",
    "title": "Generate 3D tree models as IFC",
    "description": "Creates 3D models of trees within a given bounding box as IFC file",
    "version": "1.0.0",
    "inputs": {
        "bbox": {
            "title": "Bounding box",
            "description": "Area of interest [min_x, min_y, max_x, max_y]",
            "schema": {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 4,
                "maxItems": 4,
            },
            "default": [9.9847, 53.5519, 9.9856, 53.5522],
        },
        "level_of_geom": {
            "title": "Level of geometric detail",
            "schema": {"type": "integer", "minimum": 1, "maximum": 3},
            "default": 1,
        },
        "project_name": {
            "title": "Project name",
            "schema": {"type": "string"},
            "default": "Test",
        },
    },
    "outputs": {
        "model": {
            "title": "IFC Model",
            "description": "Generated IFC file",
            "schema": {"type": "string", "contentMediaType": "application/x-step"},
        }
    },
    "links": [],
}

content_get_process_generate_city_model = {
    "id": "generate-city-model",
    "title": "Generate 3D tree models as IFC",
    "description": "Creates 3D models of trees within a given bounding box as IFC file",
    "version": "1.0.0",
    "inputs": {
        "bbox": {
            "title": "Bounding box",
            "description": "Area of interest [min_x, min_y, max_x, max_y]",
            "schema": {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 4,
                "maxItems": 4,
            },
            "default": [9.9847, 53.5519, 9.9856, 53.5522],
        },
        "level_of_geom": {
            "title": "Level of geometric detail",
            "schema": {"type": "integer", "minimum": 1, "maximum": 3},
            "default": 1,
        },
        "project_name": {
            "title": "Project name",
            "schema": {"type": "string"},
            "default": "Test",
        },
    },
    "outputs": {
        "model": {
            "title": "IFC Model",
            "description": "Generated IFC file",
            "schema": {"type": "string", "contentMediaType": "application/x-step"},
        }
    },
    "links": [],
}
