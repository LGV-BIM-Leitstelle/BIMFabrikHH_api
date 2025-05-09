import requests
import json

url = "https://gv-srv-w00186:8088/processes/generate-tree-model/execution"

headers = {"accept": "application/json", "Content-Type": "application/json"}

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

proxies = {"http": None, "https": None}
response = requests.post(url, headers=headers, data=json.dumps(data), proxies=proxies, verify=False)

if response.status_code == 200:
    try:
        print(response.json())
    except ValueError:
        print("Response is not JSON:")
        print(response.text)
else:
    print(f"Request failed with status code: {response.status_code}")
    print("Response text:", response.text)
