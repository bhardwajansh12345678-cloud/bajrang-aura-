import json
import requests
from server import load_config

def test_keys():
    cfg = load_config()
    groq_key = cfg.get("GROQ_API_KEY")
    tavily_key = cfg.get("TAVILY_API_KEY")
    
    print(f"Testing Groq Key: {groq_key[:10]}...")
    try:
        headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
        payload = {"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 10}
        resp = requests.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers, timeout=10)
        print(f"Groq Result: {resp.status_code} - {resp.text[:100]}")
    except Exception as e:
        print(f"Groq Error: {str(e)}")
        
    print(f"\nTesting Tavily Key: {tavily_key[:10]}...")
    try:
        url = "https://api.tavily.com/search"
        headers = {"Authorization": f"Bearer {tavily_key}", "Content-Type": "application/json"}
        payload = {"query": "what is ECE", "max_results": 1}
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        print(f"Tavily Result: {resp.status_code} - {resp.text[:100]}")
    except Exception as e:
        print(f"Tavily Error: {str(e)}")

if __name__ == "__main__":
    test_keys()
