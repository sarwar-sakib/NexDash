import os
import re
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz

PANEL_URL = "https://customer.nesco.gov.bd/pre/panel"
DB_FILE = "meter_history.json"
CONFIG_FILE = "meter_config.json"

# Set Bangladesh timezone
BD_TZ = pytz.timezone('Asia/Dhaka')
session = requests.Session()

def get_meter_numbers():
    """Read meter numbers from meter_config.json"""
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
            return list(config.keys())
    except FileNotFoundError:
        print("❌ meter_config.json not found! Using fallback list.")
        try:
            with open("meters.txt", "r") as f:
                return [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            return ["37005309", "37006814", "37001280", "37009693", "37005104", "37002391"]

def fetch_nesco_data(cust_no):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r1 = session.get(PANEL_URL, headers=headers, timeout=20)
        soup_page = BeautifulSoup(r1.text, "html.parser")
        
        token_tag = soup_page.find("input", {"name": "_token"})
        if not token_tag:
            return None
        
        data = {"_token": token_tag["value"], "cust_no": cust_no.strip(), "submit": "রিচার্জ হিস্ট্রি"}
        r2 = session.post(PANEL_URL, headers=headers, data=data, timeout=30)
        soup = BeautifulSoup(r2.text, "html.parser")
        
        balance_anchor = soup.find(string=re.compile("অবশিষ্ট ব্যালেন্স"))
        if not balance_anchor:
            return None
        
        label = balance_anchor.find_parent("label")
        balance_value = float(label.find_next_sibling("div").find("input")["value"])
        
        # Parse the date from the website
        date_str = label.find("span").text.strip()
        dt = datetime.strptime(date_str, "%d %B %Y %I:%M:%S %p")
        formatted_date = dt.strftime("%Y-%m-%d")
        
        return {"balance": balance_value, "date": formatted_date}
    except Exception as e:
        print(f"❌ Error scraping {cust_no}: {e}")
        return None

def main():
    # Load existing database
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            full_db = json.load(f)
    else:
        full_db = {"meter_data": {}, "last_run": {}}

    meter_data = full_db.get("meter_data", {})
    last_run = full_db.get("last_run", {})

    # Get current Bangladesh date and time
    now_bd = datetime.now(BD_TZ)
    today_bd_str = now_bd.strftime("%Y-%m-%d")
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
        web_date = current_data["date"]
        
        # ---- APPLY +1 DAY SHIFT (to match actual day) ----
        actual_date = (datetime.strptime(web_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        # -------------------------------------------------
        
        print(f"   📅 Scraped: {web_date} → Adjusted: {actual_date}, Balance: {web_balance}")
        
        # Initialize history for this meter
        if cust_no not in meter_data:
            meter_data[cust_no] = []

        history = meter_data[cust_no]

        # ---- CALCULATE USAGE FROM LAST RECORDED BALANCE ----
        if len(history) > 0:
            last_entry = history[-1]
            prev_balance = last_entry["balance"]
            if web_balance <= prev_balance:
                usage = round(prev_balance - web_balance, 2)
            else:
                # Recharge – no negative usage
                usage = 0.0
        else:
            usage = 0.0

        # ---- CHECK IF WE ALREADY HAVE AN ENTRY FOR THIS DATE ----
        existing_entry = None
        for entry in history:
            if entry["balance_date"] == actual_date:
                existing_entry = entry
                break

        if existing_entry:
            # Accumulate usage: add today's usage to existing usage
            new_usage = existing_entry["usage"] + usage
            existing_entry["balance"] = web_balance
            existing_entry["usage"] = new_usage
            existing_entry["recorded_at"] = now_bd_str
            print(f"   🔄 Updated entry for {actual_date}. Usage: {new_usage} (was {existing_entry['usage'] - usage})")
        else:
            # New entry
            history.append({
                "balance_date": actual_date,
                "balance": web_balance,
                "usage": usage,
                "recorded_at": now_bd_str
            })
            print(f"   ➕ Added new entry for {actual_date}. Usage: {usage}")

        # ALWAYS update last run timestamp
        last_run[cust_no] = now_bd_str
        print(f"   🕒 Last run updated to: {now_bd_str}")

    # Save back to file
    full_db["meter_data"] = meter_data
    full_db["last_run"] = last_run

    with open(DB_FILE, "w") as f:
        json.dump(full_db, f, indent=4)
    
    print("\n✅ Database updated successfully!")

if __name__ == "__main__":
    main()
