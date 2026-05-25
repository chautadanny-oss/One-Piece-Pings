import requests
import time
import json
import os
import sys
import hashlib
from datetime import datetime

# ============================================================
# ONEPIECEPINGS BOT v1.1
# Monitors One Piece TCG restocks across major retailers
# Crew gets instant alerts with direct link
# Free members get alert 30 minutes later without link
# Runs via GitHub Actions every 5 minutes — 24/7 365
# ============================================================

# --- WEBHOOKS (loaded from GitHub secrets) ---
CREW_WEBHOOK = os.environ.get("CREW_WEBHOOK", "")
FREE_WEBHOOK = os.environ.get("FREE_WEBHOOK", "")

# --- PRODUCTS TO MONITOR ---
# Add new products here anytime — bot handles the rest automatically
PRODUCTS = [
    # TARGET
    {
        "name": "One Piece OP-10 Royal Blood Booster Box",
        "retailer": "Target",
        "url": "https://www.target.com/p/one-piece-card-game-royal-blood-booster-box/-/A-91234567",
        "price": "$44.99",
        "in_stock_signals": ["add to cart"],
        "out_of_stock_signals": ["out of stock", "sold out"],
    },
    # AMAZON
    {
        "name": "One Piece OP-10 Royal Blood Booster Box",
        "retailer": "Amazon",
        "url": "https://www.amazon.com/dp/B0EXAMPLE123",
        "price": "$44.99",
        "in_stock_signals": ["add to cart"],
        "out_of_stock_signals": ["currently unavailable", "out of stock"],
    },
    # WALMART
    {
        "name": "One Piece TCG Booster Box OP-09",
        "retailer": "Walmart",
        "url": "https://www.walmart.com/ip/14553308605",
        "price": "$136.99",
        "in_stock_signals": ["add to cart"],
        "out_of_stock_signals": ["out of stock"],
    },
    # GAMESTOP
    {
        "name": "One Piece Premium Booster Box PRB-01",
        "retailer": "GameStop",
        "url": "https://www.gamestop.com/toys-games/trading-cards/products/one-piece-trading-card-game-premium-booster-box-20-packs/20018878.html",
        "price": "$99.99",
        "in_stock_signals": ["add to cart"],
        "out_of_stock_signals": ["out of stock", "sold out", "unavailable"],
    },
]

# --- HEADERS (mimics a real browser to avoid being blocked) ---
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# --- STATE FILE ---
# Persists between GitHub Actions runs via cache
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
    # Unique stable ID per product — never changes
    return hashlib.md5(f"{product['retailer']}-{product['name']}".encode()).hexdigest()

# --- STOCK CHECKER ---
def check_stock(product):
    try:
        response = requests.get(product["url"], headers=HEADERS, timeout=15)
        content = response.text.lower()

        for signal in product["in_stock_signals"]:
            if signal.lower() in content:
                return "IN STOCK"

        for signal in product["out_of_stock_signals"]:
            if signal.lower() in content:
                return "OUT OF STOCK"

        return "UNKNOWN"

    except Exception as e:
        print(f"[ERROR] {product['retailer']} — {product['name']}: {e}")
        return "ERROR"

# --- SEND DISCORD WEBHOOK ---
def send_webhook(webhook_url, payload):
    if not webhook_url:
        print("[WARNING] Webhook URL is empty — skipping")
        return
    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        if response.status_code in [200, 204]:
            print(f"[✅] Alert sent")
        else:
            print(f"[⚠️] Webhook failed: {response.status_code} — {response.text}")
    except Exception as e:
        print(f"[ERROR] Webhook error: {e}")

# --- CREW ALERT (instant, full info + direct link) ---
def build_crew_alert(product):
    now = datetime.utcnow().strftime("%I:%M %p UTC")
    return {
        "embeds": [
            {
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
            }
        ]
    }

# --- FREE ALERT (30 mins delayed, no direct link) ---
def build_free_alert(product):
    return {
        "embeds": [
            {
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
            }
        ]
    }

# --- MAIN RUN (single check cycle for GitHub Actions) ---
def run_once():
    print("=" * 50)
    print("  OnePiecePings Bot 🏴‍☠️")
    print(f"  {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 50)

    state = load_state()

    print(f"\n[🔍] Checking {len(PRODUCTS)} products...\n")

    for product in PRODUCTS:
        pid = get_product_id(product)
        status = check_stock(product)
        last_status = state.get(pid, "OUT OF STOCK")

        print(f"  [{status}] {product['retailer']} — {product['name']}")

        # --- NEW RESTOCK DETECTED ---
        if status == "IN STOCK" and last_status != "IN STOCK":
            print(f"  [🚨] RESTOCK! Firing Crew alert now...")
            send_webhook(CREW_WEBHOOK, build_crew_alert(product))

            # Schedule free alert 30 minutes from now
            # Stored in state so it survives across GitHub Actions runs
            state[f"{pid}_free_send_at"] = time.time() + (30 * 60)
            print(f"  [⏳] Free alert scheduled in 30 minutes")

        # --- SEND PENDING FREE ALERT IF DUE ---
        free_send_at = state.get(f"{pid}_free_send_at")
        if free_send_at and time.time() >= float(free_send_at):
            print(f"  [📢] Sending free alert for {product['name']} @ {product['retailer']}")
            send_webhook(FREE_WEBHOOK, build_free_alert(product))
            del state[f"{pid}_free_send_at"]

        # Update status in state
        state[pid] = status

    save_state(state)
    print("\n[✅] Check complete. State saved.")

# --- ENTRY POINT ---
if __name__ == "__main__":
    run_once()
