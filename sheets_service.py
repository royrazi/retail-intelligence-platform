import os
import json
import gspread
from datetime import datetime

CREDS_FILE = "google_credentials.json"
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "Smart Retail - Master Engine")

def get_sheets_client():
    try:
        if os.path.exists(CREDS_FILE):
            return gspread.service_account(filename=CREDS_FILE).open(SPREADSHEET_NAME)
        
        env_creds = os.getenv("GOOGLE_CREDENTIALS") or os.getenv("GOOGLE_CREDS_JSON") or os.getenv("GOOGLE_CREDENTIALS_JSON")
        if env_creds:
            creds_dict = json.loads(env_creds)
            return gspread.service_account_from_dict(creds_dict).open(SPREADSHEET_NAME)
            
        return None
    except Exception as e:
        print(f"[Google Sheets Auth Error]: {e}")
        return None

def append_sale_to_sheets(sale_data: dict) -> bool:
    try:
        sheet = get_sheets_client()
        if not sheet:
            return False
        
        worksheet = sheet.worksheet("עסקאות")
        now = datetime.now()
        timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S")
        month_str = now.strftime("%Y-%m")
        unique_id = f"TX-{now.strftime('%y%m%d')}-{now.strftime('%H%M%S')}"

        sale_price = float(sale_data.get("sale_price", 0))
        cost_price = float(sale_data.get("cost_price", 250))
        shipping_cost = float(sale_data.get("shipping_cost", 0))
        gross_profit = sale_price - cost_price - shipping_cost

        row = [
            unique_id,
            timestamp_str,
            month_str,
            sale_data.get("channel", "store"),
            sale_data.get("item_name", ""),
            sale_data.get("category", "מזוודות"),
            sale_price,
            cost_price,
            shipping_cost,
            sale_data.get("payment_method", "bit"),
            sale_data.get("campaign_tag", "none"),
            sale_data.get("customer_city", ""),
            gross_profit
        ]
        
        worksheet.append_row(row)
        return True
    except Exception as e:
        print(f"[Google Sheets Append Error]: {e}")
        return False

def add_campaign_spend(month: str, campaign_name: str, spend: float, notes: str = "") -> bool:
    try:
        sheet = get_sheets_client()
        if not sheet:
            return False
        
        worksheet = sheet.worksheet("הוצאות_קמפיינים")
        worksheet.append_row([month, campaign_name, float(spend), notes])
        return True
    except Exception as e:
        print(f"[Google Sheets Spend Error]: {e}")
        return False

def clear_all_sales_sheet():
    try:
        sheet = get_sheets_client()
        if sheet:
            ws = sheet.worksheet("עסקאות")
            ws.batch_clear(["A2:M1000"])
            return True
    except Exception as e:
        print(f"[Sheets Clear Error]: {e}")
        return False