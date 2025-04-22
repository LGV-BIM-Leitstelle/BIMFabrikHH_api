import requests

# url = "http://gv-srv-w00186:8084/output/Baeume_20250421_195717_da1c79c6-8ce8-46d2-84aa-80c5e77a789f.ifc"
url = "http://gv-srv-w00186:8082/output/Baeume_20250422_175110_c0972eea-8d70-4526-ad7d-1ad08e9a439e.ifc"

proxies = {
    "http": None,
    "https": None,
}
# proxies = {
#     "http": "http://10.65.108.2:3128",
#     "https": "http://10.65.108.2:3128",
# }

response = requests.get(url, proxies=proxies)

if response.status_code == 200:
    with open("downloaded_file.ifc", "wb") as f:
        f.write(response.content)
    print("File downloaded successfully.")
else:
    print(f"Failed to download. Status code: {response.status_code}")
    print(response.text)
