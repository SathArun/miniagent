import requests  # intentionally missing from requirements, no requirements.txt
respons = requests.get("https://httpbin.org/get")  # typo: respons
print(respons.status_code)
