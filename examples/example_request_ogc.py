import requests
import json

# Define the URL and headers
# url = "http://gv-srv-w00186:8084/processes/generate-tree-model/execution"
url = "https://gv-srv-w00186:8088/processes/generate-tree-model/execution"


headers = {"accept": "application/json", "Content-Type": "application/json"}

# Define the payload
data = {
    "inputs": {
        "bbox": {"min_x": 9.9756, "min_y": 53.5522, "max_x": 9.9789, "max_y": 53.5536},
        "containers": [
            {
                "containerTitle": "string",
                "containerId": "string",
                "components": {
                    "additionalProp1": {"title": "string", "value": "string"},
                    "additionalProp2": {"title": "string", "value": "string"},
                    "additionalProp3": {"title": "string", "value": "string"},
                },
            },
            {
                "containerTitle": "string",
                "containerId": "string",
                "components": {
                    "additionalProp1": {"title": "string", "value": "string"},
                    "additionalProp2": {"title": "string", "value": "string"},
                    "additionalProp3": {"title": "string", "value": "string"},
                },
            },
        ],
    }
}


# Define proxies as an empty dictionary to bypass any proxy settings
proxies = {"http": None, "https": None}

# Send POST request with no proxy
response = requests.post(url, headers=headers, data=json.dumps(data), proxies=proxies)

# Check if the response was successful (status code 200)
if response.status_code == 200:
    try:
        # Try to parse the response as JSON
        response_json = response.json()
        print(response_json)
    except ValueError:
        # Handle the case where the response is not valid JSON
        print("Response content is not in JSON format.")
        print("Response text:", response.text)
else:
    # Handle errors based on the status code
    print(f"Request failed with status code: {response.status_code}")
    print("Response text:", response.text)
