import os
import requests
from flask import Flask, jsonify
from datetime import datetime, timedelta
from requests_aws4auth import AWS4Auth

app = Flask(__name__)

# ======================================================
# STARTUP LOG
# ======================================================
print("🚀 App starting...", flush=True)

# ======================================================
# ENV VARIABLES
# ======================================================
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("AMZ_REFRESH_TOKEN")

AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")
TABLE = os.getenv("AIRTABLE_TABLE")

AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
AWS_REGION = os.getenv("AWS_REGION")

# ======================================================
# ENV CHECK
# ======================================================
print("🔐 Env check:", flush=True)
print("CLIENT_ID:", bool(CLIENT_ID), flush=True)
print("CLIENT_SECRET:", bool(CLIENT_SECRET), flush=True)
print("REFRESH_TOKEN:", bool(REFRESH_TOKEN), flush=True)
print("AIRTABLE_TOKEN:", bool(AIRTABLE_TOKEN), flush=True)
print("AWS_ACCESS_KEY:", bool(AWS_ACCESS_KEY), flush=True)
print("AWS_SECRET_KEY:", bool(AWS_SECRET_KEY), flush=True)
print("AWS_REGION:", AWS_REGION, flush=True)

# ======================================================
# AMAZON CONFIG
# ======================================================
MARKETPLACE_ID = "A2VIGQ35RCS4UG"  # UAE
# Change this line
AMAZON_API_BASE = "https://sandbox.sellingpartnerapi-eu.amazon.com"

aws_auth = AWS4Auth(
    AWS_ACCESS_KEY,
    AWS_SECRET_KEY,
    AWS_REGION,
    "execute-api"
)

# ======================================================
# AMAZON TOKEN (LWA)
# ======================================================
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
    r.raise_for_status()

    print("✅ Amazon token received", flush=True)
    return r.json()["access_token"]

# ======================================================
# AMAZON ORDERS
# ======================================================
def get_orders():
    print("📦 Fetching Amazon orders...", flush=True)

    token = get_amazon_token()

    headers = {
        "x-amz-access-token": token,
        "Content-Type": "application/json"
    }

    # created_after = (datetime.utcnow() - timedelta(days=2)).isoformat()

    # params = {
    #     "MarketplaceIds": MARKETPLACE_ID,
    #     "CreatedAfter": created_after
    # }

    url = f"{AMAZON_API_BASE}/orders/v0/orders"
    params = {"MarketplaceIds": MARKETPLACE_ID}

    r = requests.get(
        url,
        headers=headers,
        params=params,
        auth=aws_auth   # 🔥 REQUIRED
    )



    print("🟡 Orders API status:", r.status_code, flush=True)
    print("🟡 Orders API response:", r.text[:500], flush=True)

    print("🔐 x-amz-access-token:", token[:20], "...", flush=True)
    r.raise_for_status()

    orders = r.json().get("payload", {}).get("Orders", [])
    print(f"✅ Orders fetched: {len(orders)}", flush=True)

    return orders

# ======================================================
# AMAZON ORDER ITEMS
# ======================================================
def get_order_items(order_id):
    print(f"📦 Fetching items for order {order_id}", flush=True)

    token = get_amazon_token()

    headers = {
        "x-amz-access-token": token,
        "Content-Type": "application/json"
    }

    url = f"{AMAZON_API_BASE}/orders/v0/orders/{order_id}/orderItems"

    r = requests.get(
        url,
        headers=headers,
        auth=aws_auth   # 🔥 REQUIRED
    )

    print("🟡 OrderItems status:", r.status_code, flush=True)
    print("🟡 OrderItems response:", r.text[:500], flush=True)

    r.raise_for_status()

    items = r.json().get("payload", {}).get("OrderItems", [])
    print(f"✅ Items found: {len(items)}", flush=True)

    return items

# ======================================================
# ROUTES
# ======================================================

@app.route("/health")
def health():
    print("❤️ Health check", flush=True)
    return "OK", 200


@app.route("/amazon-test")
def amazon_test():
    print("📡 /amazon-test HIT", flush=True)
    token = get_amazon_token()
    return jsonify({
        "status": "amazon connected",
        "token_received": True
    })


@app.route("/airtable-test")
def airtable_test():
    print("📡 /airtable-test HIT", flush=True)

    url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE}"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}

    r = requests.get(url, headers=headers)

    print("🟡 Airtable status:", r.status_code, flush=True)
    r.raise_for_status()

    records = r.json().get("records", [])
    print(f"✅ Airtable records: {len(records)}", flush=True)

    return jsonify({
        "status": "airtable connected",
        "records": len(records)
    })


@app.route("/amazon-orders-test")
def amazon_orders_test():
    try:
        token = get_amazon_token()
        headers = {
            "x-amz-access-token": token,
            "Content-Type": "application/json"
        }
        params = {
             "MarketplaceIds": "ATVPDKIKX0DER",  # US marketplace for sandbox
             "CreatedAfter": "2023-01-01T00:00:00Z"
        }
        r = requests.get(
            f"{AMAZON_API_BASE}/orders/v0/orders",
            headers=headers,
            params=params,
            auth=aws_auth
        )
        print("🟡 Orders API status:", r.status_code, flush=True)
        print("🟡 Orders API response:", r.text[:500], flush=True)
        r.raise_for_status()
        orders = r.json().get("payload", {}).get("Orders", [])
        return jsonify({"status": "ok", "count": len(orders), "orders": orders})
    except Exception as e:
        print("❌ Error:", str(e), flush=True)
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)