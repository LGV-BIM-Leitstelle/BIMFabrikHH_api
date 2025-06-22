import time
import requests
import json

BASE_URI = "http://localhost:8084"

url = f"{BASE_URI}/processes/generate-tree-model/execution"

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

resp_data = None

if response.status_code == 200:
    try:
        resp_data = response.json()
        print(resp_data)
    except ValueError:
        print("Response is not JSON:")
        print(response.text)
else:
    print(f"Request failed with status code: {response.status_code}")
    print("Response text:", response.text)


url = f"{BASE_URI}/jobs/{resp_data['id']}/results"

dl_url = None

for i in range(10):
    time.sleep(1.)
    response = requests.get(url, proxies=proxies)

    if response.status_code == 200:
        try:
            dl_url = response.json()['url-http']
            print(dl_url)
            break
        except (ValueError, KeyError):
            print(response.text)
    else:
        print(f"Failed to download. Status code: {response.status_code}")
        print(response.text)

response = requests.get(f"{BASE_URI}/{dl_url}", proxies=proxies)

if response.status_code == 200:
    with open('downloaded-file.ifc', 'w') as f:
        f.write(response.text)
else:
    print(f"Failed to download. Status code: {response.status_code}")
    print(response.text)