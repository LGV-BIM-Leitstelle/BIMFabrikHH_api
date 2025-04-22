import requests

url = "http://gv-srv-w00186:8084/output/Baeume_20250421_195717_da1c79c6-8ce8-46d2-84aa-80c5e77a789f.ifc"

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
