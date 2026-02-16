import os
import requests
from flask import Flask, jsonify

app = Flask(__name__)

# ======================
# AMAZON CREDENTIALS
# ======================
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("AMZ_REFRESH_TOKEN")
SELLER_ID = os.getenv("AMZ_SELLER_ID")

# ======================
# AIRTABLE CREDENTIALS
# ======================
AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")
TABLE = os.getenv("AIRTABLE_TABLE")

# ======================
# AMAZON TOKEN
# ======================
def get_amazon_token():
    url = "https://api.amazon.com/auth/o2/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": REFRESH_TOKEN,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }
    r = requests.post(url, data=data)
    r.raise_for_status()
    return r.json()["access_token"]

# ======================
# TEST AMAZON CONNECTION
# ======================
@app.route("/amazon-test")
def amazon_test():
    token = get_amazon_token()
    return jsonify({
        "status": "amazon connected",
        "token_received": bool(token)
    })

# ======================
# TEST AIRTABLE CONNECTION
# ======================
@app.route("/airtable-test")
def airtable_test():
    url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}"
    }
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return jsonify({
        "status": "airtable connected",
        "records": len(r.json().get("records", []))
    })

# ======================
# HEALTH
# ======================
@app.route("/health")
def health():
    return "OK", 200
