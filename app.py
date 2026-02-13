import os
import requests
from flask import Flask, jsonify

app = Flask(__name__)

# ========== ENV ==========
AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")
ORDERS_TABLE = os.getenv("AIRTABLE_ORDERS_TABLE")

# =========================
# AMAZON TOKEN
# =========================
def get_amazon_access_token():
    url = "https://api.amazon.com/auth/o2/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": os.getenv("AMAZON_REFRESH_TOKEN"),
        "client_id": os.getenv("AMAZON_CLIENT_ID"),
        "client_secret": os.getenv("AMAZON_CLIENT_SECRET")
    }
    return requests.post(url, data=data).json()["access_token"]

# =========================
# AMAZON ORDERS
# =========================
def fetch_amazon_orders(token):
    url = "https://sellingpartnerapi-na.amazon.com/orders/v0/orders"
    headers = {
        "x-amz-access-token": token,
        "Content-Type": "application/json"
    }
    params = {
        "MarketplaceIds": os.getenv("AMAZON_MARKETPLACE_ID")
    }
    res = requests.get(url, headers=headers, params=params)
    return res.json().get("payload", {}).get("Orders", [])

# =========================
# AIRTABLE PUSH
# =========================
def push_to_airtable(order):
    url = f"https://api.airtable.com/v0/{BASE_ID}/{ORDERS_TABLE}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "fields": {
            "Order ID": order["AmazonOrderId"],
            "Status": order["OrderStatus"]
        }
    }
    requests.post(url, json=data, headers=headers)

# =========================
# API ENDPOINT
# =========================
@app.route("/amazon/sync", methods=["POST"])
def sync():
    token = get_amazon_access_token()
    orders = fetch_amazon_orders(token)

    for order in orders:
        push_to_airtable(order)

    return jsonify({"synced": len(orders)})
