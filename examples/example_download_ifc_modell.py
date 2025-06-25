import requests

url = "http://gv-srv-w00186:8084/output/Baeume_20250422_175110_c0972eea-8d70-4526-ad7d-1ad08e9a439e.ifc"

# test

proxies = {
    "http": None,
    "https": None,
}

response = requests.get(url, proxies=proxies)

if response.status_code == 200:
    with open("downloaded_file.ifc", "wb") as f:
        f.write(response.content)
    print("File downloaded successfully.")
else:
    print(f"Failed to download. Status code: {response.status_code}")
    print(response.text)
