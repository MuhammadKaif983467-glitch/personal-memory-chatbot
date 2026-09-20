"""Test the universal import endpoints."""
import requests

BASE = "http://localhost:8000"

def test_health():
    r = requests.get(f"{BASE}/health", timeout=5)
    d = r.json()
    print(f"HEALTH: {r.status_code} version={d.get('version')} chat={d.get('chat_auth_configured')}")
    return r.status_code == 200

def test_inspect():
    csv_data = "sender,message,timestamp\nAli,hello,2025-09-01 10:30\nZahid,hi,2025-09-01 10:31"
    files = {"file": ("test.csv", csv_data.encode("utf-8"), "text/csv")}
    r = requests.post(f"{BASE}/import/universal/inspect", files=files, timeout=10)
    print(f"INSPECT: {r.status_code} {r.json()}")
    return r.status_code == 200

def test_preview():
    csv_data = "sender,message,timestamp\nAli,bro kya scene,2025-09-01 10:30\nZahid,bas theek,2025-09-01 10:31\nAli,aur bata,2025-09-01 10:32"
    files = {"file": ("test.csv", csv_data.encode("utf-8"), "text/csv")}
    data = {"person": ""}
    r = requests.post(f"{BASE}/import/universal/preview", files=files, data=data, timeout=10)
    d = r.json()
    print(f"PREVIEW: {r.status_code} platform={d.get('platform')} participants={d.get('participants')} valid={d.get('valid_messages')}")
    for p in d.get("preview", []):
        print(f"  {p['sender']}: {p['content']}")
    return r.status_code == 200

def test_import():
    csv_data = "sender,message,timestamp\nAli,hello there,2025-09-01 10:30\nZahid,hi buddy,2025-09-01 10:31"
    files = {"file": ("test.csv", csv_data.encode("utf-8"), "text/csv")}
    data = {"person": "Ali", "consent_confirmed": "true"}
    print("Sending import request...")
    r = requests.post(f"{BASE}/import/universal", files=files, data=data, timeout=60)
    print(f"IMPORT status: {r.status_code}")
    print(f"IMPORT text: {r.text[:500]}")
    try:
        d = r.json()
        print(f"IMPORT ok={d.get('ok')} person={d.get('person_name')} imported={d.get('imported')} total={d.get('total')}")
    except Exception as e:
        print(f"IMPORT json parse failed: {e}")
    return r.status_code == 200

if __name__ == "__main__":
    print("=== Testing Universal Import Engine ===\n")
    test_health()
    print()
    test_inspect()
    print()
    test_preview()
    print()
    test_import()
    print("\n=== Done ===")
