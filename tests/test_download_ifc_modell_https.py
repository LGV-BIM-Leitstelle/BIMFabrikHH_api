import requests

url = "https://gv-srv-w00186:8088/output/Baeume_20250509_164545_c0592bf9-1c98-4451-aa28-1b7e10bb6a94.ifc"

proxies = {
    "http": None,
    "https": None,
}

response = requests.get(url, proxies=proxies, verify=False)

if response.status_code == 200:
    with open("downloaded_file.ifc", "wb") as f:
        f.write(response.content)
    print("File downloaded successfully.")
else:
    print(f"Failed to download. Status code: {response.status_code}")
    print(response.text)
