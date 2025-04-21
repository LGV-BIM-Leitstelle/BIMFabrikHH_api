# content_get_processes = {
#     "processes": [
#         {
#             "id": "get-trees",
#             "title": "Get Trees",
#             "description": "Retrieve tree data from OGC API Features Hamburg",
#             "version": "1.0.0",
#             "jobControlOptions": ["async-execute"],
#             "outputTransmission": ["value"],
#         },
#         {
#             "id": "generate-tree-model",
#             "title": "Generate Tree Model",
#             "description": "Generate an IFC model of trees within the specified bounding box",
#             "version": "1.0.0",
#             "jobControlOptions": ["async-execute"],
#             "outputTransmission": ["value"],
#         },
#     ]
# }
#
#
# content_get_process_get_trees = {
#     "id": "get-trees",
#     "title": "Get Trees",
#     "description": "Retrieve tree data from OGC API Features Hamburg",
#     "version": "1.0.0",
#     "inputs": {
#         "bbox": {
#             "title": "Bounding Box",
#             "description": "Bounding box coordinates [min_x, min_y, max_x, max_y]",
#             "schema": {
#                 "type": "array",
#                 "items": {"type": "number"},
#                 "minItems": 4,
#                 "maxItems": 4,
#             },
#             "minOccurs": 1,
#             "maxOccurs": 1,
#         },
#         "crs": {
#             "title": "CRS",
#             "description": "Coordinate reference system",
#             "schema": {"type": "string"},
#             "minOccurs": 0,
#             "maxOccurs": 1,
#         },
#         "limit": {
#             "title": "Limit",
#             "description": "Maximum number of features to return",
#             "schema": {"type": "integer"},
#             "minOccurs": 0,
#             "maxOccurs": 1,
#         },
#         "skip_geometry": {
#             "title": "Skip Geometry",
#             "description": "Skip geometry in response",
#             "schema": {"type": "boolean"},
#             "minOccurs": 0,
#             "maxOccurs": 1,
#         },
#     },
#     "outputs": {
#         "trees": {
#             "title": "Trees Data",
#             "description": "GeoJSON data of trees",
#             "schema": {"type": "object"},
#         }
#     },
#     "jobControlOptions": ["async-execute"],
#     "outputTransmission": ["value"],
# }
#
# content_get_process_generate_tree_model = {
#     "id": "generate-tree-model",
#     "title": "Generate Tree Model",
#     "description": "Generate an IFC model of trees within the specified bounding box",
#     "version": "1.0.0",
#     "inputs": {
#         "bbox": {
#             "title": "Bounding Box",
#             "description": "Bounding box coordinates [min_x, min_y, max_x, max_y]",
#             "schema": {
#                 "type": "array",
#                 "items": {"type": "number"},
#                 "minItems": 4,
#                 "maxItems": 4,
#             },
#             "minOccurs": 1,
#             "maxOccurs": 1,
#         },
#         "level_of_geom": {
#             "title": "Level of Geometry",
#             "description": "Level of geometry detail (1-3)",
#             "schema": {"type": "integer", "minimum": 1, "maximum": 3},
#             "minOccurs": 0,
#             "maxOccurs": 1,
#         },
#         "project_name": {
#             "title": "Project Name",
#             "description": "Project name for the IFC file",
#             "schema": {"type": "string"},
#             "minOccurs": 0,
#             "maxOccurs": 1,
#         },
#     },
#     "outputs": {
#         "model": {
#             "title": "IFC Model",
#             "description": "IFC file containing tree models",
#             "schema": {
#                 "type": "string",
#                 "contentMediaType": "application/x-step",
#             },
#         }
#     },
#     "jobControlOptions": ["async-execute"],
#     "outputTransmission": ["value"],
# }
