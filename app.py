import os
import requests
from flask import Flask, jsonify

app = Flask(__name__)

print("🚀 App starting...")

# ======================
# AMAZON CREDENTIALS
# ======================
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("AMZ_REFRESH_TOKEN")
SELLER_ID = os.getenv("AMZ_SELLER_ID")

print("🔐 Amazon Env Check")
print("CLIENT_ID:", "✅ SET" if CLIENT_ID else "❌ MISSING")
print("CLIENT_SECRET:", "✅ SET" if CLIENT_SECRET else "❌ MISSING")
print("REFRESH_TOKEN:", "✅ SET" if REFRESH_TOKEN else "❌ MISSING")
print("SELLER_ID:", "✅ SET" if SELLER_ID else "❌ MISSING")

# ======================
# AIRTABLE CREDENTIALS
# ======================
AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")
TABLE = os.getenv("AIRTABLE_TABLE")

print("📦 Airtable Env Check")
print("AIRTABLE_TOKEN:", "✅ SET" if AIRTABLE_TOKEN else "❌ MISSING")
print("BASE_ID:", "✅ SET" if BASE_ID else "❌ MISSING")
print("TABLE:", "✅ SET" if TABLE else "❌ MISSING")

# ======================
# AMAZON TOKEN
# ======================
def get_amazon_token():
    print("🔑 Requesting Amazon access token...")

    url = "https://api.amazon.com/auth/o2/token"
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": REFRESH_TOKEN,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }

    response = requests.post(url, data=payload)

    print("🟡 Amazon Token Status Code:", response.status_code)
    print("🟡 Amazon Token Response:", response.text)

    response.raise_for_status()

    token = response.json().get("access_token")
    print("✅ Amazon token received")

    return token

# ======================
# AMAZON TEST
# ======================
@app.route("/amazon-test")
def amazon_test():
    print("📡 /amazon-test endpoint hit")

    try:
        token = get_amazon_token()
        return jsonify({
            "status": "amazon connected",
            "token_received": bool(token)
        })

    except Exception as e:
        print("❌ Amazon test failed:", str(e))
        return jsonify({"error": str(e)}), 500

# ======================
# AIRTABLE TEST
# ======================
@app.route("/airtable-test")
def airtable_test():
    print("📡 /airtable-test endpoint hit")

    try:
        url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE}"
        headers = {
            "Authorization": f"Bearer {AIRTABLE_TOKEN}"
        }

        print("🔍 Airtable URL:", url)

        response = requests.get(url, headers=headers)

        print("🟡 Airtable Status Code:", response.status_code)
        print("🟡 Airtable Response:", response.text)

        response.raise_for_status()

        records = response.json().get("records", [])
        print(f"✅ Airtable connected, records found: {len(records)}")

        return jsonify({
            "status": "airtable connected",
            "records": len(records)
        })

    except Exception as e:
        print("❌ Airtable test failed:", str(e))
        return jsonify({"error": str(e)}), 500

# ======================
# HEALTH
# ======================
@app.route("/health")
def health():
    print("❤️ Health check hit")
    return "OK", 200
