import requests

try:
    res = requests.post("http://127.0.0.1:8000/chat", json={"text": "Hello"})
    print("Status code:", res.status_code)
    print("Response:", res.json())
except Exception as e:
    print("Error:", e)
