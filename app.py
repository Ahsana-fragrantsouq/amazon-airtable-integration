import os
import requests
from flask import Flask, jsonify
from datetime import datetime, timedelta

app = Flask(__name__)

# ======================================================
# ENV
# ======================================================

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("AMZ_REFRESH_TOKEN")

AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
AWS_REGION = os.getenv("AWS_REGION")

AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")

# ======================================================
# TABLE IDS
# ======================================================

ORDERS_TABLE_ID = "Orders"
CUSTOMERS_TABLE_ID = "Customers"
FRENCH_INVENTORIES_TABLE_ID = "French Inventories"
ORDER_LINE_ITEMS_TABLE_ID = "Order Line items"

# ======================================================
# AMAZON CONFIG
# ======================================================

MARKETPLACE_ID = "A2VIGQ35RCS4UG"
AMAZON_API_BASE = "https://sellingpartnerapi-eu.amazon.com"

# ======================================================
# START LOG
# ======================================================

print("🚀 Amazon Airtable Sync Starting...", flush=True)

# ======================================================
# AMAZON TOKEN
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

    token = r.json()["access_token"]

    print("✅ Amazon token received", flush=True)

    return token

# ======================================================
# AMAZON REQUEST
# ======================================================

def amazon_get(endpoint, token, params=None):

    headers = {
        "x-amz-access-token": token,
        "Content-Type": "application/json"
    }

    url = f"{AMAZON_API_BASE}{endpoint}"

    r = requests.get(
        url,
        headers=headers,
        params=params
    )

    print(f"🟡 Amazon GET {endpoint} → {r.status_code}", flush=True)

    if r.status_code != 200:
        print(r.text, flush=True)

    r.raise_for_status()

    return r.json()

# ======================================================
# GET AMAZON ORDERS
# ======================================================

def get_amazon_orders(token):

    created_after = (
        datetime.utcnow() - timedelta(days=2)
    ).isoformat()

    params = {
        "MarketplaceIds": MARKETPLACE_ID,
        "CreatedAfter": created_after
    }

    data = amazon_get(
        "/orders/v0/orders",
        token,
        params
    )

    orders = data.get("payload", {}).get("Orders", [])

    print(f"✅ Orders fetched: {len(orders)}", flush=True)

    return orders

# ======================================================
# GET ORDER ITEMS
# ======================================================

def get_amazon_order_items(token, order_id):

    data = amazon_get(
        f"/orders/v0/orders/{order_id}/orderItems",
        token
    )

    items = data.get("payload", {}).get("OrderItems", [])

    print(
        f"📦 Items fetched for {order_id}: {len(items)}",
        flush=True
    )

    return items

# ======================================================
# AIRTABLE HEADERS
# ======================================================

def airtable_headers():

    return {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type": "application/json"
    }

# ======================================================
# AIRTABLE SEARCH
# ======================================================

def airtable_search(table, formula):

    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{table}"

    r = requests.get(
        url,
        headers=airtable_headers(),
        params={
            "filterByFormula": formula
        }
    )

    r.raise_for_status()

    return r.json().get("records", [])

# ======================================================
# AIRTABLE CREATE
# ======================================================

def airtable_create(table, fields):

    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{table}"

    r = requests.post(
        url,
        headers=airtable_headers(),
        json={
            "fields": fields
        }
    )

    print(f"✅ Airtable CREATE {table}", flush=True)

    if r.status_code >= 400:
        print(r.text, flush=True)

    r.raise_for_status()

    return r.json()

# ======================================================
# AIRTABLE UPDATE
# ======================================================

def airtable_update(table, record_id, fields):

    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{table}/{record_id}"

    r = requests.patch(
        url,
        headers=airtable_headers(),
        json={
            "fields": fields
        }
    )

    print(f"🔄 Airtable UPDATE {table}", flush=True)

    if r.status_code >= 400:
        print(r.text, flush=True)

    r.raise_for_status()

    return r.json()

# ======================================================
# PAYMENT STATUS
# ======================================================

def map_payment(order_status):

    if order_status.lower() in [
        "shipped",
        "delivered",
        "unshipped"
    ]:
        return "Paid"

    if order_status.lower() in [
        "canceled",
        "cancelled"
    ]:
        return "Cancelled"

    return "Pending"

# ======================================================
# SHIPPING STATUS
# ======================================================

def map_shipping(order_status):

    if order_status.lower() in [
        "shipped",
        "delivered"
    ]:
        return "Shipped"

    if order_status.lower() in [
        "canceled",
        "cancelled"
    ]:
        return "Cancelled"

    return "New"

# ======================================================
# CUSTOMER
# ======================================================

def get_or_create_customer(order, token):

    buyer_name = order.get("BuyerInfo", {}).get(
        "BuyerName",
        "Amazon Customer"
    )

    amazon_order_id = order.get("AmazonOrderId", "")

    print(f"👤 Customer lookup: {buyer_name}", flush=True)

    records = airtable_search(
        CUSTOMERS_TABLE_ID,
        f"{{Amazon Id}}='{amazon_order_id}'"
    )

    # ======================================================
    # EXISTING CUSTOMER
    # ======================================================

    if records:

        record_id = records[0]["id"]

        print(
            f"✅ Existing customer found",
            flush=True
        )

        return record_id

    # ======================================================
    # CREATE CUSTOMER
    # ======================================================

    result = airtable_create(
        CUSTOMERS_TABLE_ID,
        {
            "Name": buyer_name,
            "Amazon Id": amazon_order_id
        }
    )

    print(
        f"✅ New customer created",
        flush=True
    )

    return result["id"]

# ======================================================
# FIND PRODUCT BY SKU
# ======================================================

def find_product_by_sku(sku):

    if not sku:
        return None

    records = airtable_search(
        FRENCH_INVENTORIES_TABLE_ID,
        f"{{SKU}}='{sku}'"
    )

    if records:

        print(f"✅ SKU linked: {sku}", flush=True)

        return records[0]["id"]

    print(f"⚠ SKU not found: {sku}", flush=True)

    return None

# ======================================================
# ORDERS TABLE
# ======================================================

def get_or_create_order(order_id, customer_id, order_date, pay, ship, ship_by):

    print(f"📋 Orders table lookup | {order_id}", flush=True)

    records = airtable_search(
        ORDERS_TABLE_ID,
        f"{{Order ID}}='{order_id}'"
    )

    # ======================================================
    # UPDATE EXISTING
    # ======================================================

    if records:

        existing_id = records[0]["id"]

        update_fields = {
            "Payment Status": pay,
            "Shipping Status": ship,
        }

        if ship_by:
            update_fields["Ship By"] = ship_by

        airtable_update(
            ORDERS_TABLE_ID,
            existing_id,
            update_fields
        )

        print(
            f"🔄 Existing order updated",
            flush=True
        )

        return existing_id

    # ======================================================
    # CREATE NEW
    # ======================================================

    fields = {
        "Order ID": order_id,
        "Order Date": order_date,
        "Payment Status": pay,
        "Shipping Status": ship,
        "Sales Channel": "Amazon",
    }

    if customer_id:
        fields["Customer"] = [customer_id]

    if ship_by:
        fields["Ship By"] = ship_by

    result = airtable_create(
        ORDERS_TABLE_ID,
        fields
    )

    print(
        f"✅ New order created",
        flush=True
    )

    return result["id"]

# ======================================================
# ORDER LINE ITEM EXISTING CHECK
# ======================================================

def get_existing_line(order_id, sku):

    formula = (
        f"AND("
        f"{{Order ID}}='{order_id}',"
        f"{{Item SKU}}='{sku}'"
        f")"
    )

    records = airtable_search(
        ORDER_LINE_ITEMS_TABLE_ID,
        formula
    )

    return records[0]["id"] if records else None

# ======================================================
# BUILD ORDER LINE ITEM
# ======================================================

def build_line_fields(
    order_id,
    product_title,
    order_date,
    qty,
    price,
    sku,
    pay,
    ship,
    ship_by,
    customer_id,
    orders_record_id,
    product_record_id
):

    fields = {
        "Order ID": order_id,
        "Order Number": order_id,
        "Amazon Product Name": product_title,
        "Order Date": order_date,
        "Qty": qty,
        "Rate": price,
        "Item SKU": sku,
        "Sales Channel": "Amazon",
        "Payment Status": pay,
        "Shipping Status": ship,
        "Ship By": ship_by,
    }

    if customer_id:
        fields["Customer"] = [customer_id]

    if orders_record_id:
        fields["Order"] = [orders_record_id]

    if product_record_id:
        fields["Product"] = [product_record_id]

    return fields

# ======================================================
# PROCESS ORDER
# ======================================================

def process_order(order, token):

    order_id = order.get("AmazonOrderId", "")
    order_status = order.get("OrderStatus", "")
    order_date = order.get("PurchaseDate", "")[:10]

    pay = map_payment(order_status)
    ship = map_shipping(order_status)

    # ======================================================
    # SHIP BY
    # ======================================================

    ship_by = ""

    latest_ship_date = order.get("LatestShipDate", "")

    if latest_ship_date:
        ship_by = latest_ship_date[:10]

    if not ship_by and order_status.lower() in [
        "shipped",
        "delivered"
    ]:
        ship_by = datetime.utcnow().strftime("%Y-%m-%d")

    print(
        f"\n📦 Processing order {order_id}",
        flush=True
    )

    # ======================================================
    # CUSTOMER
    # ======================================================

    customer_id = get_or_create_customer(
        order,
        token
    )

    # ======================================================
    # ORDERS TABLE
    # ======================================================

    orders_record_id = get_or_create_order(
        order_id,
        customer_id,
        order_date,
        pay,
        ship,
        ship_by
    )

    # ======================================================
    # AMAZON ITEMS
    # ======================================================

    items = get_amazon_order_items(
        token,
        order_id
    )

    # ======================================================
    # LOOP ITEMS
    # ======================================================

    for item in items:

        product_title = item.get("Title", "")
        sku = item.get("SellerSKU", "")

        qty = int(
            item.get("QuantityOrdered", 1)
        )

        price = float(
            item.get("ItemPrice", {})
            .get("Amount", 0)
        )

        product_record_id = find_product_by_sku(sku)

        existing_id = get_existing_line(
            order_id,
            sku
        )

        fields = build_line_fields(
            order_id,
            product_title,
            order_date,
            qty,
            price,
            sku,
            pay,
            ship,
            ship_by,
            customer_id,
            orders_record_id,
            product_record_id
        )

        # ======================================================
        # UPDATE
        # ======================================================

        if existing_id:

            airtable_update(
                ORDER_LINE_ITEMS_TABLE_ID,
                existing_id,
                fields
            )

            print(
                f"🔄 Updated line item",
                flush=True
            )

        # ======================================================
        # CREATE
        # ======================================================

        else:

            airtable_create(
                ORDER_LINE_ITEMS_TABLE_ID,
                fields
            )

            print(
                f"✅ Created line item",
                flush=True
            )

# ======================================================
# MAIN SYNC
# ======================================================

@app.route("/sync-amazon")
def sync_amazon():

    try:

        print(
            "\n🚀 START AMAZON SYNC",
            flush=True
        )

        token = get_amazon_token()

        orders = get_amazon_orders(token)

        for order in orders:

            try:
                process_order(order, token)

            except Exception as e:
                print(
                    f"❌ Order processing failed: {e}",
                    flush=True
                )

        print(
            "✅ AMAZON SYNC COMPLETE",
            flush=True
        )

        return jsonify({
            "status": "success",
            "orders": len(orders)
        })

    except Exception as e:

        print(
            f"❌ SYNC FAILED: {e}",
            flush=True
        )

        return jsonify({
            "error": str(e)
        }), 500

# ======================================================
# HEALTH
# ======================================================

@app.route("/health")
def health():
    return "OK", 200

# ======================================================
# RUN
# ======================================================

if __name__ == "__main__":
    app.run(debug=True)