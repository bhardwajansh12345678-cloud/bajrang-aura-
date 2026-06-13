import json
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8000"
PASS = 0
FAIL = 0


def post(path, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BASE + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, json.loads(resp.read().decode())


def get(path):
    req = urllib.request.Request(BASE + path, method="GET")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, resp.read().decode()


def post_raw(path, raw_body):
    req = urllib.request.Request(
        BASE + path,
        data=raw_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def check(name, condition):
    global PASS, FAIL
    if condition:
        print(f"  PASS: {name}")
        PASS += 1
    else:
        print(f"  FAIL: {name}")
        FAIL += 1


def main():
    global PASS, FAIL
    print("=" * 50)
    print("Bajrang Aura - Test Suite")
    print("=" * 50)

    print("\n[1] GET /index.html")
    code, body = get("/index.html")
    check("Status 200", code == 200)
    check("Contains wake word", "Jai Shree Ram" in body)
    check("Contains chat area", "chat-area" in body)
    check("Contains life lesson btn", "lifeLessonBtn" in body)

    print("\n[2] POST /chat - normal")
    code, data = post("/chat", {"text": "Hello"})
    check("Status 200", code == 200)
    check("Has response key", "response" in data)
    check("Response non-empty", len(data.get("response", "")) > 0)
    print(f"    Response: {data.get('response', '')[:100]}")

    print("\n[3] POST /chat - empty text")
    code, data = post_raw("/chat", json.dumps({"text": ""}).encode())
    check("Returns 400", code == 400)
    check("Has error key", "error" in data)

    print("\n[4] POST /chat - invalid JSON")
    code, data = post_raw("/chat", b"not json")
    check("Returns 400", code == 400)
    check("Has error key", "error" in data)

    print("\n[5] POST /life-lesson - Ramayana")
    code, data = post("/life-lesson", {"topic": "Ramayana", "problem": "I feel lost"})
    check("Status 200", code == 200)
    check("Has response key", "response" in data)
    resp = data.get("response", "")
    check("References Ramayana", "Ramayana" in resp)
    check("Has source refs", "Source:" in resp)
    lesson_count = resp.count("Source:")
    check(f"Returns {lesson_count} lessons", lesson_count >= 1)
    print(f"    Preview: {resp[:120]}...")

    print("\n[6] POST /life-lesson - Mahabharata")
    code, data = post(
        "/life-lesson", {"topic": "Mahabharata", "problem": "anger management"}
    )
    check("Status 200", code == 200)
    resp = data.get("response", "")
    check("References Mahabharata", "Mahabharata" in resp)
    check("Has source refs", "Source:" in resp)

    print("\n[7] POST /life-lesson - Gita")
    code, data = post("/life-lesson", {"topic": "Gita", "problem": "detachment"})
    check("Status 200", code == 200)
    resp = data.get("response", "")
    check("References Gita", "Gita" in resp)

    print("\n[8] POST /life-lesson - no topic (aggregate)")
    code, data = post("/life-lesson", {"topic": "", "problem": "general guidance"})
    check("Status 200", code == 200)
    resp = data.get("response", "")
    check("Aggregates sources", "Ramayana/Mahabharata/Gita" in resp)

    print("\n[9] POST /life-lesson - invalid JSON")
    code, data = post_raw("/life-lesson", b"bad")
    check("Returns 400", code == 400)

    print("\n[10] POST /unknown - 404")
    try:
        code, data = post("/unknown", {"text": "test"})
        check("Returns 404", code == 404)
    except urllib.error.HTTPError as e:
        check("Returns 404", e.code == 404)

    print("\n" + "=" * 50)
    print(f"Results: {PASS} passed, {FAIL} failed")
    print("=" * 50)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
