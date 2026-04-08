import os
import requests
import threading
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from requests_aws4auth import AWS4Auth

requests.adapters.DEFAULT_RETRIES = 3

app = Flask(__name__)

# ======================================================
# CONFIG
# ======================================================
AIRTABLE_TOKEN            = os.getenv("AIRTABLE_TOKEN")
BASE_ID                   = os.getenv("BASE_ID")
CUSTOMERS_TABLE_ID        = os.getenv("CUSTOMERS_TABLE")
ORDER_LINE_ITEMS_TABLE_ID = os.getenv("ORDER_LINE_ITEMS_TABLE")
AIRTABLE_URL              = "https://api.airtable.com/v0"
REQUEST_TIMEOUT           = 30

AMZ_CLIENT_ID     = os.getenv("CLIENT_ID")
AMZ_CLIENT_SECRET = os.getenv("CLIENT_SECRET")
AMZ_REFRESH_TOKEN = os.getenv("AMZ_REFRESH_TOKEN")
AWS_ACCESS_KEY    = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY    = os.getenv("AWS_SECRET_KEY")
AWS_REGION        = os.getenv("AWS_REGION", "eu-west-1")
MARKETPLACE_ID    = "A2VIGQ35RCS4UG"  # UAE

AMZ_PRODUCTION = os.getenv("AMZ_PRODUCTION", "false").lower() == "true"
AMAZON_API_BASE = (
    "https://sellingpartnerapi-eu.amazon.com"
    if AMZ_PRODUCTION else
    "https://sandbox.sellingpartnerapi-eu.amazon.com"
)

AIRTABLE_HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_TOKEN}",
    "Content-Type":  "application/json"
}

aws_auth = AWS4Auth(AWS_ACCESS_KEY, AWS_SECRET_KEY, AWS_REGION, "execute-api")
amazon_lock = threading.Lock()

# ======================================================
# STARTUP LOG
# ======================================================
print("🚀 App starting...", flush=True)
print(f"🌍 Amazon mode: {'PRODUCTION' if AMZ_PRODUCTION else 'SANDBOX'}", flush=True)
print("AIRTABLE_TOKEN:",    bool(AIRTABLE_TOKEN), flush=True)
print("BASE_ID:",           bool(BASE_ID), flush=True)
print("CUSTOMERS_TABLE:",   bool(CUSTOMERS_TABLE_ID), flush=True)
print("ORDER_LINE_ITEMS:",  bool(ORDER_LINE_ITEMS_TABLE_ID), flush=True)
print("CLIENT_ID:",         bool(AMZ_CLIENT_ID), flush=True)
print("AWS_ACCESS_KEY:",    bool(AWS_ACCESS_KEY), flush=True)

# ======================================================
# AIRTABLE HELPERS
# ======================================================
def airtable_search(table_id, formula):
    print(f"🔍 Searching | formula={formula}", flush=True)
    r = requests.get(
        f"{AIRTABLE_URL}/{BASE_ID}/{table_id}",
        headers=AIRTABLE_HEADERS,
        params={"filterByFormula": formula},
        timeout=REQUEST_TIMEOUT
    )
    r.raise_for_status()
    records = r.json().get("records", [])
    print(f"🔍 Found {len(records)} records", flush=True)
    return records

def airtable_create(table_id, fields):
    print(f"📝 Creating | fields={list(fields.keys())}", flush=True)
    r = requests.post(
        f"{AIRTABLE_URL}/{BASE_ID}/{table_id}",
        headers=AIRTABLE_HEADERS,
        json={"fields": fields},
        timeout=REQUEST_TIMEOUT
    )
    if r.status_code >= 400:
        print("❌ Create error:", r.text, flush=True)
        r.raise_for_status()
    print("✅ Record created", flush=True)
    return r.json()

def airtable_update(table_id, record_id, fields):
    print(f"✏️ Updating {record_id}", flush=True)
    r = requests.patch(
        f"{AIRTABLE_URL}/{BASE_ID}/{table_id}/{record_id}",
        headers=AIRTABLE_HEADERS,
        json={"fields": fields},
        timeout=REQUEST_TIMEOUT
    )
    if r.status_code >= 400:
        print("❌ Update error:", r.text, flush=True)
        r.raise_for_status()
    print("✅ Record updated", flush=True)

# ======================================================
# AMAZON HELPERS
# ======================================================
def get_amazon_token():
    print("🔑 Getting Amazon token...", flush=True)
    r = requests.post(
        "https://api.amazon.com/auth/o2/token",
        data={
            "grant_type":    "refresh_token",
            "refresh_token": AMZ_REFRESH_TOKEN,
            "client_id":     AMZ_CLIENT_ID,
            "client_secret": AMZ_CLIENT_SECRET,
        },
        timeout=REQUEST_TIMEOUT
    )
    r.raise_for_status()
    print("✅ Amazon token received", flush=True)
    return r.json()["access_token"]

def get_amazon_orders(token):
    print("📦 Fetching Amazon orders...", flush=True)
    if AMZ_PRODUCTION:
        params = {
            "MarketplaceIds": MARKETPLACE_ID,
            "CreatedAfter":   (datetime.utcnow() - timedelta(days=2)).isoformat()
        }
    else:
        params = {
            "MarketplaceIds": "ATVPDKIKX0DER",
            "CreatedAfter":   "TEST_CASE_200"
        }
    r = requests.get(
        f"{AMAZON_API_BASE}/orders/v0/orders",
        headers={"x-amz-access-token": token, "Content-Type": "application/json"},
        params=params,
        auth=aws_auth,
        timeout=REQUEST_TIMEOUT
    )
    print("🟡 Orders status:", r.status_code, flush=True)
    print("🟡 Orders response:", r.text[:300], flush=True)
    r.raise_for_status()
    orders = r.json().get("payload", {}).get("Orders", [])
    print(f"✅ Amazon orders fetched: {len(orders)}", flush=True)
    return orders

def get_amazon_order_items(token, order_id):
    print(f"📦 Fetching items for {order_id}", flush=True)
    r = requests.get(
        f"{AMAZON_API_BASE}/orders/v0/orders/{order_id}/orderItems",
        headers={"x-amz-access-token": token, "Content-Type": "application/json"},
        auth=aws_auth,
        timeout=REQUEST_TIMEOUT
    )
    print("🟡 Items status:", r.status_code, flush=True)
    r.raise_for_status()
    items = r.json().get("payload", {}).get("OrderItems", [])
    print(f"✅ Items found: {len(items)}", flush=True)
    return items

def map_shipping(status):
    s = status.lower()
    if s == "shipped":               return "Shipped"
    if s == "delivered":             return "Delivered"
    if s in ["unshipped", "pending"]:return "New"
    return "New"

def map_payment(status):
    s = status.lower()
    if s in ["shipped", "delivered"]: return "Paid"
    if s == "canceled":               return "Failed"
    return "Pending"

def get_or_create_customer(order):
    buyer_info = order.get("BuyerInfo", {})
    buyer_id   = buyer_info.get("BuyerEmail", "").strip()
    buyer_name = buyer_info.get("BuyerName", "Amazon Customer").strip()

    # Sandbox orders have no BuyerInfo — use order ID as fallback
    if not buyer_id:
        buyer_id   = order.get("AmazonOrderId", "")
        buyer_name = "Amazon Customer (Sandbox)"

    print(f"👤 Customer lookup | id={buyer_id}", flush=True)

    records = airtable_search(CUSTOMERS_TABLE_ID, f"{{Amazon Id}}='{buyer_id}'")
    if records:
        print("👤 Existing customer found", flush=True)
        return records[0]["id"]

    print("👤 Creating new customer...", flush=True)
    result = airtable_create(CUSTOMERS_TABLE_ID, {
        "Name":      buyer_name,
        "Amazon Id": buyer_id
    })
    return result["id"]

def get_existing_line(order_id, product_name):
    records = airtable_search(
        ORDER_LINE_ITEMS_TABLE_ID,
        f"AND({{Order ID}}='{order_id}', {{Amazon Product Name}}='{product_name}')"
    )
    return records[0]["id"] if records else None

# ======================================================
# MAIN SYNC JOB
# ======================================================
def sync_amazon_orders_job():
    if not amazon_lock.acquire(blocking=False):
        print("⏳ Sync already running — skipped", flush=True)
        return

    print(f"⏰ Amazon sync started ({'PRODUCTION' if AMZ_PRODUCTION else 'SANDBOX'})", flush=True)

    try:
        token  = get_amazon_token()
        orders = get_amazon_orders(token)

        for order in orders:
            order_id     = order.get("AmazonOrderId", "")
            order_status = order.get("OrderStatus", "")
            order_date   = order.get("PurchaseDate", "")[:10]
            pay          = map_payment(order_status)
            ship         = map_shipping(order_status)

            print(f"📦 Processing {order_id} | {order_status}", flush=True)

            customer_id = get_or_create_customer(order)

            try:
                items = get_amazon_order_items(token, order_id)
            except Exception as e:
                print(f"❌ Items fetch failed for {order_id}: {e}", flush=True)
                continue

            for item in items:
                product = item.get("Title", "")
                qty     = int(item.get("QuantityOrdered", 1))
                price   = float(item.get("ItemPrice", {}).get("Amount", 0))

                existing_id = get_existing_line(order_id, product)

                if existing_id:
                    airtable_update(ORDER_LINE_ITEMS_TABLE_ID, existing_id, {
                        "Payment Status":  pay,
                        "Shipping Status": ship
                    })
                    print(f"🔄 Updated {order_id} → {product}", flush=True)
                else:
                    airtable_create(ORDER_LINE_ITEMS_TABLE_ID, {
                        "Order ID":            order_id,
                        "Order Number":        order_id,
                        "Amazon Product Name": product,
                        "Customer":            [customer_id],
                        "Order Date":          order_date,
                        "Qty":                 qty,
                        "Rate":                price,
                        "Sales Channel":       "Amazon",
                        "Payment Status":      pay,
                        "Shipping Status":     ship,
                    })
                    print(f"✅ Created {order_id} → {product}", flush=True)

    except Exception as e:
        print("❌ Sync error:", e, flush=True)

    finally:
        amazon_lock.release()
        print("🎉 Amazon sync finished", flush=True)

# ======================================================
# ROUTES
# ======================================================
@app.route("/", methods=["GET", "HEAD"])
def health():
    return "OK", 200

@app.route("/wake", methods=["GET"])
def wake():
    return "awake", 200

@app.route("/ping", methods=["GET"])
def ping():
    print("🔥 /ping HIT", flush=True)
    # Comment out auth temporarily for testing
    # if request.headers.get("X-Update-Secret") != os.getenv("UPDATE_SECRET"):
    #     return jsonify({"error": "Unauthorized"}), 401
    thread = threading.Thread(target=sync_amazon_orders_job)
    thread.daemon = True
    thread.start()
    return jsonify({
        "status": "Sync started",
        "mode":   "PRODUCTION" if AMZ_PRODUCTION else "SANDBOX"
    }), 200

@app.route("/debug")
def debug():
    token = AIRTABLE_TOKEN or ""
    return jsonify({
        "token_length": len(token),
        "token_start": token[:10] if token else "EMPTY",
        "token_starts_with_pat": token.startswith("pat"),
        "base_id": BASE_ID,
        "customers_table": CUSTOMERS_TABLE_ID,
        "order_line_items_table": ORDER_LINE_ITEMS_TABLE_ID,
    })

# ======================================================
# RUN
# ======================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)