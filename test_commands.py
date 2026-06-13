import requests

tests = [
    "open calculator",
    "play shape of you on spotify",
    "check battery",
    "take a note to buy milk",
    "volume up",
    "read my notes",
]

for t in tests:
    r = requests.post("http://127.0.0.1:8000/chat", json={"text": t}).json()
    print(f"[{t}]")
    print(f"  source={r['source']!r}  reply={r['response'][:70]!r}")
    print()
