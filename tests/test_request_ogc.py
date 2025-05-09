import requests
import json

# Step 1: Create the bounding box
bbox_params = {"min_x": 9.9847, "min_y": 53.5519, "max_x": 9.9856, "max_y": 53.5522}

# Step 2: Define the containers and components
project_info = {
    "containerTitle": "Pset_ProjectInformation",
    "containerId": "project_info_container",
    "components": {
        "project_name": {"title": "project_name", "value": "Test_MyProject"},
        "site_name": {"title": "site_name", "value": "Test_MySite"},
        "building_name": {"title": "building_name", "value": "Test_MyBuilding"},
    },
}

level_of_geo = {
    "containerTitle": "Level_Of_Geometry",
    "containerId": "level_of_geo",
    "components": {"level_of_geo": {"title": "level_of_geom", "value": 1}},
}

# Step 3: Create the request body with the 'input' key
request_body_example = {"input": {"bbox": bbox_params, "containers": [project_info, level_of_geo]}}

# Step 4: Send the POST request to the server
url = "http://gv-srv-w00186:8084/processes/generate-tree-model/execution"

headers = {
    "Content-Type": "application/json",
}

# Step 5: Convert the dictionary to a JSON string
payload = json.dumps(request_body_example)

# Send the request
response = requests.post(url, headers=headers, data=payload)

# Check the response status
if response.status_code == 200:
    print("Request successful!")
    print("Response:", response.json())
else:
    print(f"Error: {response.status_code}, {response.text}")
