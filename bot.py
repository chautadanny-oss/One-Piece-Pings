import requests
import time
import json
import os
import hashlib
from datetime import datetime

# ============================================================
# ONEPIECEPINGS BOT v2.0
# Uses retailer APIs directly instead of scraping HTML
# This is how real monitor bots work — faster and more reliable
# Crew gets instant alerts, Free members get alert 30 mins later
# ============================================================

CREW_WEBHOOK = os.environ.get("CREW_WEBHOOK", "")
FREE_WEBHOOK = os.environ.get("FREE_WEBHOOK", "")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

# ============================================================
# PRODUCTS LIST
# Each product has a custom check_fn that hits the right API
# To add a new product just copy a block and update the IDs
# ============================================================

def check_target(tcin):
    """Target's internal API — returns real stock data"""
    url = f"https://redsky.target.com/redsky_aggregations/v1/web/pdp_client_v1?key=9f36aeafbe60771e321a7cc95a78140772ab3e96&tcin={tcin}&pricing_store_id=3991"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()
        avail = data["data"]["product"]["fulfillment"]["shipping_options"]["availability_status"]
        return "IN STOCK" if avail == "IN_STOCK" else "OUT OF STOCK"
    except Exception as e:
        print(f"    [ERROR] Target API: {e}")
        return "UNKNOWN"

def check_walmart(item_id):
    """Walmart's internal API"""
    url = f"https://www.walmart.com/ip/{item_id}"
    headers = {**HEADERS, "Accept": "text/html"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        content = r.text.lower()
        if '"availabilitystatustype":"available"' in content or '"availability":"in_stock"' in content:
            return "IN STOCK"
        if '"availabilitystatustype":"not_available"' in content or "out of stock" in content:
            return "OUT OF STOCK"
        return "UNKNOWN"
    except Exception as e:
        print(f"    [ERROR] Walmart: {e}")
        return "UNKNOWN"

def check_gamestop(product_id):
    """GameStop product availability"""
    url = f"https://www.gamestop.com/toys-games/trading-cards/products/{product_id}.html"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        content = r.text.lower()
        if "add to cart" in content and "out of stock" not in content:
            return "IN STOCK"
        if "out of stock" in content or "sold out" in content or "exclusively in stores" in content.lower():
            return "OUT OF STOCK"
        return "UNKNOWN"
    except Exception as e:
        print(f"    [ERROR] GameStop: {e}")
        return "UNKNOWN"

def check_amazon(asin):
    """Amazon product page"""
    url = f"https://www.amazon.com/dp/{asin}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        content = r.text.lower()
        if "add to cart" in content or "buy now" in content:
            return "IN STOCK"
        if "currently unavailable" in content or "out of stock" in content:
            return "OUT OF STOCK"
        return "UNKNOWN"
    except Exception as e:
        print(f"    [ERROR] Amazon: {e}")
        return "UNKNOWN"

# ============================================================
# PRODUCTS TO MONITOR
# tcin = Target's product ID (found in the URL after /A-)
# item_id = Walmart's product ID (found in the URL after /ip/)
# asin = Amazon's product ID (found in URL after /dp/)
# ============================================================

PRODUCTS = [
    # --- TARGET ---
    {
        "name": "One Piece TCG: Adventure on Kami's Island Booster Box (OP-15)",
        "retailer": "Target",
        "price": "$44.99",
        "url": "https://www.target.com/p/2026-one-piece-tcg-adventure-on-kami-s-island-booster-box-op-15/-/A-1011542319",
        "check": lambda: check_target("1011542319"),
    },
    {
        "name": "One Piece Card Game: Treasure Booster Set",
        "retailer": "Target",
        "price": "$34.99",
        "url": "https://www.target.com/p/one-piece-card-game-treasure-booster-set/-/A-91669423",
        "check": lambda: check_target("91669423"),
    },

    # --- AMAZON ---
    {
        "name": "One Piece TCG: Royal Bloodline (OP-10) Booster Box",
        "retailer": "Amazon",
        "price": "$44.99",
        "url": "https://www.amazon.com/dp/B0F1DX55D1",
        "check": lambda: check_amazon("B0F1DX55D1"),
    },
    {
        "name": "One Piece TCG: A Fist of Divine Speed (OP-11) Booster Box",
        "retailer": "Amazon",
        "price": "$44.99",
        "url": "https://www.amazon.com/dp/B0F85QYZJ6",
        "check": lambda: check_amazon("B0F85QYZJ6"),
    },
    {
        "name": "BANDAI OP-10 One Piece Royal Blood Booster Box 24 Packs",
        "retailer": "Amazon",
        "price": "$44.99",
        "url": "https://www.amazon.com/dp/B0DDWZWW1Z",
        "check": lambda: check_amazon("B0DDWZWW1Z"),
    },

    # --- WALMART ---
    {
        "name": "One Piece TCG: Legacy of the Master (OP-12) Booster Box",
        "retailer": "Walmart",
        "price": "$44.99",
        "url": "https://www.walmart.com/ip/16861004932",
        "check": lambda: check_walmart("16861004932"),
    },
    {
        "name": "One Piece TCG: Heroines Edition Booster Box (EB-03)",
        "retailer": "Walmart",
        "price": "$44.99",
        "url": "https://www.walmart.com/ip/18101660354",
        "check": lambda: check_walmart("18101660354"),
    },

    # --- GAMESTOP ---
    {
        "name": "One Piece TCG: Legacy of the Master Booster Box (OP-12)",
        "retailer": "GameStop",
        "price": "$44.99",
        "url": "https://www.gamestop.com/toys-games/trading-cards/products/one-piece-trading-card-game-legacy-of-the-master-booster-box-op-12-24-boosters/20026856.html",
        "check": lambda: check_gamestop("one-piece-trading-card-game-legacy-of-the-master-booster-box-op-12-24-boosters/20026856"),
    },
    {
        "name": "One Piece TCG: Fist of Divine Speed Booster Box (OP-11)",
        "retailer": "GameStop",
        "price": "$44.99",
        "url": "https://www.gamestop.com/toys-games/trading-cards/products/one-piece-card-game-fist-of-divine-speed-booster-box-op-11/20023052.html",
        "check": lambda: check_gamestop("one-piece-card-game-fist-of-divine-speed-booster-box-op-11/20023052"),
    },
]

# ============================================================
# STATE MANAGEMENT
# ============================================================

STATE_FILE = "state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def get_product_id(product):
    return hashlib.md5(f"{product['retailer']}-{product['name']}".encode()).hexdigest()

# ============================================================
# DISCORD ALERTS
# ============================================================

def send_webhook(webhook_url, payload):
    if not webhook_url:
        print("    [WARNING] Webhook URL missing — check GitHub secrets")
        return
    try:
        r = requests.post(webhook_url, json=payload, timeout=10)
        if r.status_code in [200, 204]:
            print(f"    [✅] Alert sent")
        else:
            print(f"    [⚠️] Webhook error: {r.status_code}")
    except Exception as e:
        print(f"    [ERROR] Webhook failed: {e}")

def build_crew_alert(product):
    now = datetime.utcnow().strftime("%I:%M %p UTC")
    return {
        "embeds": [{
            "title": "🚨 CREW ALERT",
            "color": 0xFFD700,
            "fields": [
                {"name": "📦 Product", "value": product["name"], "inline": True},
                {"name": "🏪 Retailer", "value": product["retailer"], "inline": True},
                {"name": "💰 Price", "value": product["price"], "inline": True},
                {"name": "✅ Status", "value": "IN STOCK", "inline": True},
                {"name": "📊 Stock Level", "value": "Limited — move fast", "inline": True},
                {"name": "⏰ Detected", "value": now, "inline": True},
                {"name": "🔗 Direct Link", "value": f"[Click to checkout]({product['url']})", "inline": False},
            ],
            "footer": {"text": "OnePiecePings Crew • You got here first ⚡"},
            "timestamp": datetime.utcnow().isoformat(),
        }]
    }

def build_free_alert(product):
    return {
        "embeds": [{
            "title": "🔔 RESTOCK ALERT",
            "color": 0x3498DB,
            "fields": [
                {"name": "📦 Product", "value": product["name"], "inline": True},
                {"name": "🏪 Retailer", "value": product["retailer"], "inline": True},
                {"name": "💰 Price", "value": product["price"], "inline": True},
                {"name": "✅ Status", "value": "IN STOCK", "inline": True},
                {"name": "📊 Stock Level", "value": "Limited", "inline": True},
                {"name": "🕐 Heads up", "value": "This drop went live 30 minutes ago.", "inline": False},
                {
                    "name": "⚡ Want to be first next time?",
                    "value": "Upgrade to **Crew** — instant alerts + direct checkout links the second drops go live.\n👉 [Join Crew on OnePiecePings](https://whop.com/onepiecepings)",
                    "inline": False,
                },
            ],
            "footer": {"text": "OnePiecePings • Free Access"},
            "timestamp": datetime.utcnow().isoformat(),
        }]
    }

# ============================================================
# MAIN
# ============================================================

def run_once():
    print("=" * 50)
    print("  OnePiecePings Bot 🏴‍☠️")
    print(f"  {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 50)

    state = load_state()
    print(f"\n[🔍] Checking {len(PRODUCTS)} products...\n")

    for product in PRODUCTS:
        pid = get_product_id(product)
        status = product["check"]()
        last_status = state.get(pid, "OUT OF STOCK")

        print(f"  [{status}] {product['retailer']} — {product['name']}")

        # New restock detected
        if status == "IN STOCK" and last_status != "IN STOCK":
            print(f"  [🚨] RESTOCK! Firing Crew alert...")
            send_webhook(CREW_WEBHOOK, build_crew_alert(product))
            state[f"{pid}_free_send_at"] = time.time() + (30 * 60)
            print(f"  [⏳] Free alert queued for 30 minutes")

        # Send pending free alert if due
        free_send_at = state.get(f"{pid}_free_send_at")
        if free_send_at and time.time() >= float(free_send_at):
            print(f"  [📢] Sending free alert...")
            send_webhook(FREE_WEBHOOK, build_free_alert(product))
            del state[f"{pid}_free_send_at"]

        state[pid] = status

    save_state(state)
    print("\n[✅] Done. State saved.")

if __name__ == "__main__":
    run_once()
