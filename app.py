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
        
        date_str = label.find("span").text.strip()
        dt = datetime.strptime(date_str, "%d %B %Y %I:%M:%S %p")
        formatted_date = dt.strftime("%Y-%m-%d")
        
        return {"balance": balance_value, "date": formatted_date}
    except Exception as e:
        print(f"❌ Error scraping {cust_no}: {e}")
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
        web_date = current_data["date"]
        
        # ---- Apply +1 day shift ----
        actual_date = (datetime.strptime(web_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        # -----------------------------
        
        print(f"   📅 Scraped: {web_date} → Adjusted: {actual_date}, Balance: {web_balance}")
        
        if cust_no not in meter_data:
            meter_data[cust_no] = []

        history = meter_data[cust_no]

        # ---- FIND THE LAST RECORDED ENTRY (ANY DATE) ----
        if len(history) > 0:
            last_entry = history[-1]
            prev_balance = last_entry["balance"]
            prev_date = last_entry["balance_date"]
            
            # Calculate usage: previous balance - current balance
            if web_balance <= prev_balance:
                usage = round(prev_balance - web_balance, 2)
            else:
                # Recharge happened – usage is 0 (no negative consumption)
                usage = 0.0
        else:
            # No history yet – first entry
            usage = 0.0

        # ---- CHECK IF WE ALREADY HAVE AN ENTRY FOR THIS DATE ----
        existing_entry = None
        for entry in history:
            if entry["balance_date"] == actual_date:
                existing_entry = entry
                break

        if existing_entry:
            # UPDATE existing entry (accumulate usage)
            old_usage = existing_entry["usage"]
            new_usage = old_usage + usage  # Add today's consumption
            existing_entry["balance"] = web_balance
            existing_entry["usage"] = new_usage
            existing_entry["recorded_at"] = now_bd_str
            print(f"   🔄 Updated entry for {actual_date}. Usage: {new_usage} (was {old_usage})")
        else:
            # ADD new entry
            history.append({
                "balance_date": actual_date,
                "balance": web_balance,
                "usage": usage,
                "recorded_at": now_bd_str
            })
            print(f"   ➕ Added new entry for {actual_date}. Usage: {usage}")

        last_run[cust_no] = now_bd_str
        print(f"   🕒 Last run updated to: {now_bd_str}")

    full_db["meter_data"] = meter_data
    full_db["last_run"] = last_run

    with open(DB_FILE, "w") as f:
        json.dump(full_db, f, indent=4)
    
    print("\n✅ Database updated successfully!")

if __name__ == "__main__":
    main()        soup_page = BeautifulSoup(r1.text, "html.parser")
        
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
            # Still update last_run to know it was checked (even on failure)
            last_run[cust_no] = now_bd_str
            continue

        web_balance = current_data["balance"]
        web_date = current_data["date"]
        
        print(f"   📅 Web Date: {web_date}, Balance: {web_balance}")
        
        # Initialize list for this meter if not exists
        if cust_no not in meter_data:
            meter_data[cust_no] = []

        history = meter_data[cust_no]

        # ---- Compare web date with today ----
        if web_date == today_bd_str:
            print("   ✅ Server has updated for today.")
            
            # Calculate usage from the last known balance
            if len(history) > 0:
                last_entry = history[-1]
                prev_balance = last_entry["balance"]
                # If current balance is lower, consumption happened
                if web_balance <= prev_balance:
                    usage = round(prev_balance - web_balance, 2)
                else:
                    # Recharge happened, no negative usage
                    usage = 0.0
            else:
                usage = 0.0

            # Check if we already have an entry for today's web_date
            if len(history) > 0 and history[-1]["balance_date"] == web_date:
                # Overwrite the last entry (balance should be same, but update timestamp)
                history[-1] = {
                    "balance_date": web_date,
                    "balance": web_balance,
                    "usage": usage,
                    "recorded_at": now_bd_str
                }
                print(f"   🔄 Updated today's entry. Usage: {usage}")
            else:
                # Append new entry
                history.append({
                    "balance_date": web_date,
                    "balance": web_balance,
                    "usage": usage,
                    "recorded_at": now_bd_str
                })
                print(f"   ➕ Added new entry for {web_date}. Usage: {usage}")
        else:
            print(f"   ⏳ Server date ({web_date}) does not match today ({today_bd_str}). Skipping balance update.")

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
