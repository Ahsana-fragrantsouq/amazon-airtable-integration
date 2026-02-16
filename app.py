import os
import requests
from flask import Flask, jsonify

app = Flask(__name__)

print("🚀 App starting...", flush=True)

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("AMZ_REFRESH_TOKEN")

AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")
TABLE = os.getenv("AIRTABLE_TABLE")

print("🔐 Env check:", flush=True)
print("CLIENT_ID:", bool(CLIENT_ID), flush=True)
print("CLIENT_SECRET:", bool(CLIENT_SECRET), flush=True)
print("REFRESH_TOKEN:", bool(REFRESH_TOKEN), flush=True)
print("AIRTABLE_TOKEN:", bool(AIRTABLE_TOKEN), flush=True)

def get_amazon_token():
    print("🔑 Requesting Amazon token...", flush=True)

    r = requests.post(
        "https://api.amazon.com/auth/o2/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": REFRESH_TOKEN,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        }
    )

    print("🟡 Amazon token status:", r.status_code, flush=True)
    print("🟡 Amazon token response:", r.text, flush=True)

    r.raise_for_status()
    return r.json()["access_token"]

@app.route("/airtable-test")
def airtable_test():
    print("📡 /airtable-test HIT", flush=True)

    url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE}"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}

    r = requests.get(url, headers=headers)

    print("🟡 Airtable status:", r.status_code, flush=True)
    print("🟡 Airtable response length:", len(r.text), flush=True)

    r.raise_for_status()

    records = r.json().get("records", [])
    print(f"✅ Airtable records: {len(records)}", flush=True)

    return jsonify({"status": "airtable connected", "records": len(records)})

@app.route("/health")
def health():
    print("❤️ Health check", flush=True)
    return "OK", 200
