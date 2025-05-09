import requests

# proxies = {"http": "http://10.65.108.2:3128", "https": "http://10.65.108.2:3128"}
proxies = {
    "http": None,
    "https": None,
}
# url = "http://gv-srv-w00186:8083/oaf-trees?min_x=9.9733&min_y=53.5544&max_x=9.9756&max_y=53.5556"
url = "https://gv-srv-w00186:8088/bimfabrikhh-datasets/oaf-trees?min_x=9.9733&min_y=53.5544&max_x=9.9756&max_y=53.5556"

response = requests.get(url, proxies=proxies, verify=False, timeout=30)
# response = requests.get(url, verify=False)  # No proxy

if response.status_code == 200:
    try:
        data = response.json()
        print(data)
    except ValueError:
        print("Response is not in valid JSON format:", response.text)
else:
    print("Failed request:", response.status_code, response.text)
