import requests

url = "http://127.0.0.1:8001/generate-tree-model"
data = {
    "min_lon": 9.9847,
    "min_lat": 53.5519,
    "max_lon": 9.9856,
    "max_lat": 53.5522,
    "level_of_geom": 1,
    "project_name": "Projektname",
}

response = requests.post(url, json=data)
print(response.status_code)
print(response.text)
