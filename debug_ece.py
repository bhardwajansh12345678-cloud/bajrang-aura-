import json
import re
from pathlib import Path
from server import process_chat, load_config

def test_ece():
    print("Testing 'what is ece' locally...")
    resp, source, web_results = process_chat("what is ece")
    print(f"Source: {source}")
    print(f"Response: {resp}")
    print(f"Web Results Count: {len(web_results)}")

if __name__ == "__main__":
    test_ece()
