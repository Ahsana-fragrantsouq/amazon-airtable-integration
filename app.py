import os
import requests
import boto3
from flask import Flask, jsonify
from requests_aws4auth import AWS4Auth

app = Flask(__name__)

# ======================================================
# CONFIG
# ======================================================
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
SELLER_ID = os.getenv("SELLER_ID")

AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
ROLE_ARN = os.getenv("ROLE_ARN")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE = os.getenv("AIRTABLE_TABLE")

print("🚀 App starting...")
print("🔧 AWS REGION:", AWS_REGION)

# ======================================================
# 1️⃣ LWA TOKEN
# ======================================================
def get_lwa_token():
    print("🔐 Requesting LWA token...")
    url = "https://api.amazon.com/auth/o2/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "sellingpartnerapi::migration"
    }

    r = requests.post(url, data=payload, timeout=30)
    print("🔐 LWA response status:", r.status_code)
    r.raise_for_status()

    token = r.json()["access_token"]
    print("✅ LWA token received")
    return token

# ======================================================
# 2️⃣ AWS ROLE ASSUME
# ======================================================
def assume_role():
    print("🔑 Assuming AWS role...")
    sts = boto3.client(
        "sts",
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        region_name=AWS_REGION
    )

    res = sts.assume_role(
        RoleArn=ROLE_ARN,
        RoleSessionName="spapi-session"
    )

    print("✅ AWS role assumed successfully")
    return res["Credentials"]

# ======================================================
# 3️⃣ AMAZON SP-API CALL
# ======================================================
def get_orders():
    print("📦 Fetching orders from Amazon SP-API...")
    lwa_token = get_lwa_token()
    creds = assume_role()

    auth = AWS4Auth(
        creds["AccessKeyId"],
        creds["SecretAccessKey"],
        AWS_REGION,
        "execute-api",
        session_token=creds["SessionToken"]
    )

    headers = {
        "x-amz-access-token": lwa_token,
        "Content-Type": "application/json"
    }

    url = "https://sellingpartnerapi-na.amazon.com/orders/v0/orders"
    params = {
        "MarketplaceIds": "ATVPDKIKX0DER"
    }

    r = requests.get(url, headers=headers, auth=auth, params=params, timeout=30)
    print("📦 SP-API response status:", r.status_code)
    r.raise_for_status()

    print("✅ Orders fetched successfully")
    return r.json()

# ======================================================
# 4️⃣ AIRTABLE PUSH
# ======================================================
def push_to_airtable(order_id):
    print(f"📤 Pushing Order {order_id} to Airtable...")
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "fields": {
            "Order ID": order_id
        }
    }

    r = requests.post(url, json=payload, headers=headers, timeout=30)
    print(f"📤 Airtable response ({order_id}):", r.status_code)

# ======================================================
# 5️⃣ FLASK ROUTES
# ======================================================
@app.route("/health")
def health():
    print("❤️ Health check hit")
    return jsonify({"status": "ok"})

@app.route("/sync")
def sync():
    print("🚀 Sync started...")
    data = get_orders()

    orders = data.get("payload", {}).get("Orders", [])
    print(f"📊 Total orders received: {len(orders)}")

    for order in orders:
        push_to_airtable(order["AmazonOrderId"])

    print("🏁 Sync completed")
    return jsonify({
        "status": "success",
        "orders_synced": len(orders)
    })

# ======================================================
# RUN
# ======================================================
if __name__ == "__main__":
    print("🔥 Flask server running...")
    app.run(host="0.0.0.0", port=5000)
