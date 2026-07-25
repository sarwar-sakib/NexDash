import os
import json
import requests
from datetime import datetime
import pytz

# NESCO API Endpoint (Used by the Telegram Bot & Mobile App)
API_URL = "https://prepaid.nesco.gov.bd/api/v1/customer-balance/{cust_no}"
DB_FILE = "meter_history.json"
CONFIG_FILE = "meter_config.json"

BD_TZ = pytz.timezone('Asia/Dhaka')
session = requests.Session()

def get_meter_numbers():
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
            return list(config.keys())
    except FileNotFoundError:
        try:
            with open("meters.txt", "r") as f:
                return [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            return ["37005309", "37006814", "37001280", "37009693", "37005104", "37002391"]

def fetch_nesco_data(cust_no):
    """
    Fetches balance data directly via NESCO's REST API.
    Bypasses HTML parsing and anti-bot measures.
    """
    try:
        # Full Chrome User-Agent header prevents 403 Forbidden errors
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://prepaid.nesco.gov.bd/",
            "Origin": "https://prepaid.nesco.gov.bd"
        }
        
        url = API_URL.format(cust_no=cust_no.strip())
        response = session.get(url, headers=headers, timeout=20)

        if response.status_code == 200:
            data = response.json()
            
            # Safe extraction of balance from JSON response
            balance_value = float(data.get("balance", 0.0))
            
            # Format the date as YYYY-MM-DD (matches your original db format)
            reading_time = data.get("readingTime")
            if reading_time:
                try:
                    dt = datetime.strptime(reading_time, "%Y-%m-%d %H:%M:%S")
                    formatted_date = dt.strftime("%Y-%m-%d")
                except ValueError:
                    formatted_date = datetime.now(BD_TZ).strftime("%Y-%m-%d")
            else:
                formatted_date = datetime.now(BD_TZ).strftime("%Y-%m-%d")

            return {"balance": balance_value, "date": formatted_date}
        else:
            print(f"❌ API returned status code {response.status_code} for meter {cust_no}")
            return None

    except Exception as e:
        print(f"❌ Error fetching meter {cust_no}: {e}")
        return None

def main():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            full_db = json.load(f)
    else:
        full_db = {"meter_data": {}, "last_run": {}}

    meter_data = full_db.get("meter_data", {})
    last_run = full_db.get("last_run", {})

    now_bd = datetime.now(BD_TZ)
    now_bd_str = now_bd.strftime("%Y-%m-%d %H:%M:%S")

    meters = get_meter_numbers()
    print(f"⏰ Runner Time (BD): {now_bd_str}")

    for cust_no in meters:
        print(f"\n🔍 Checking meter: {cust_no}")
        current_data = fetch_nesco_data(cust_no)
        if not current_data:
            last_run[cust_no] = now_bd_str
            continue

        web_balance = current_data["balance"]
        web_date = current_data["date"]   # no shift – use as-is

        print(f"   📅 Scraped Date: {web_date}, Balance: {web_balance}")

        if cust_no not in meter_data:
            meter_data[cust_no] = []

        history = meter_data[cust_no]

        # ---- Check if we already have an entry for this date ----
        existing_idx = None
        for i, entry in enumerate(history):
            if entry["balance_date"] == web_date:
                existing_idx = i
                break

        # ---- Calculate usage from last recorded balance (if any) ----
        if len(history) > 0:
            last_entry = history[-1]
            prev_balance = last_entry["balance"]
            if web_balance <= prev_balance:
                usage = round(prev_balance - web_balance, 2)
            else:
                usage = 0.0
        else:
            usage = 0.0

        # ---- Only update if balance has changed OR no entry exists for this date ----
        if existing_idx is not None:
            existing_entry = history[existing_idx]
            if existing_entry["balance"] != web_balance:
                new_usage = existing_entry["usage"] + usage
                existing_entry["balance"] = web_balance
                existing_entry["usage"] = new_usage
                existing_entry["recorded_at"] = now_bd_str
                print(f"   🔄 Updated entry for {web_date}. New usage: {new_usage}")
            else:
                print(f"   ⏭️ Balance unchanged for {web_date}. No update needed.")
        else:
            # No entry for this date – add new one
            history.append({
                "balance_date": web_date,
                "balance": web_balance,
                "usage": usage,
                "recorded_at": now_bd_str
            })
            print(f"   ➕ Added new entry for {web_date}. Usage: {usage}")

        # Always update last run
        last_run[cust_no] = now_bd_str
        print(f"   🕒 Last run updated to: {now_bd_str}")

    full_db["meter_data"] = meter_data
    full_db["last_run"] = last_run

    with open(DB_FILE, "w") as f:
        json.dump(full_db, f, indent=4)

    print("\n✅ Database updated successfully!")

if __name__ == "__main__":
    main()
