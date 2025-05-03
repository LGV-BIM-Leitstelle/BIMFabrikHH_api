import requests

proxies = {"http": None, "https": None}


url = "https://gv-srv-w00186:8088/oaf-citymodell-tiles?min_x=9.9733&min_y=53.5544&max_x=9.9756&max_y=53.5556"
response = requests.get(url, proxies=proxies, verify=False)

if response.status_code == 200:
    try:
        data = response.json()
        print(data)
    except ValueError:
        print("Response is not in valid JSON format:", response.text)
else:
    print("Failed request:", response.status_code, response.text)
