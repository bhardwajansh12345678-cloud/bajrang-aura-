import requests
import json

api_key = "AIzaSyBckZ8Ubq0XHAppj8S_LObwK2VCt3jpfdU"
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent?key={api_key}"

payload = {
    "contents": [{"parts": [{"text": "Hello, how are you?"}]}]
}

try:
    response = requests.post(url, json=payload)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print("Success! AI Response:")
        print(data['candidates'][0]['content']['parts'][0]['text'])
    else:
        print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
