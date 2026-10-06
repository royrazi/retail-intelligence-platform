import os
import sys
import sqlite3
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

try:
    from zoneinfo import ZoneInfo
except ImportError:
    pass

from database import init_db, insert_sale
from analytics_engine import get_analytics, normalize_channel
from sheets_service import append_sale_to_sheet, sync_sheets_to_db, get_sheets_client, SPREADSHEET_NAME, SHEET_HEADERS
from telegram_service import send_telegram_monthly_report

app = FastAPI(title="Smart Retail Engine")
security = HTTPBasic()

app.mount("/static", StaticFiles(directory="static"), name="static")

# Fail-Fast Security Logic
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

if not ADMIN_USERNAME or not ADMIN_PASSWORD:
    print("CRITICAL SECURITY ERROR: ADMIN_USERNAME or ADMIN_PASSWORD missing from .env!")
    print("Fail-Fast: Shutting down the server to prevent unauthorized access.")
    sys.exit(1)

def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    if credentials.username != ADMIN_USERNAME or credentials.password != ADMIN_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

@app.on_event("startup")
def on_startup():
    init_db()
    try:
        sync_sheets_to_db()
    except Exception as e:
        print(f"Startup Google Sheets sync error: {e}")

    scheduler = BackgroundScheduler()
    scheduler.add_job(send_telegram_monthly_report, 'cron', day=1, hour=9, minute=0)
    scheduler.start()

@app.api_route("/", methods=["GET", "HEAD"])
def root_health():
    return {"status": "ok", "service": "smart-retail-engine"}

@app.api_route("/store", methods=["GET", "HEAD"])
def get_store_page():
    return FileResponse("static/store.html")

@app.api_route("/online", methods=["GET", "HEAD"])
def get_online_page():
    return FileResponse("static/online.html")

@app.api_route("/dashboard", methods=["GET", "HEAD"])
def get_dashboard_page(user: str = Depends(authenticate)):
    return FileResponse("static/dashboard.html")

@app.post("/api/sales")
async def create_sale(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}

    try:
        tz = ZoneInfo("Asia/Jerusalem")
    except:
        tz = None
    now_str = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    
    raw_channel = data.get("channel", "חנות")
    channel_heb = normalize_channel(raw_channel)
    
    prod_name = (
        data.get("item_name") or 
        data.get("product_name") or 
        data.get("product") or 
        data.get("item") or 
        "פריט כללי"
    )
    
    def parse_float(val):
        try:
            if val is None or str(val).strip() == "":
                return 0.0
            return float(val)
        except (ValueError, TypeError):
            return 0.0

    s_price = parse_float(data.get("sale_price") or data.get("selling_price") or data.get("price"))
    c_price = parse_float(data.get("cost_price") or data.get("cost"))
    d_fee = parse_float(data.get("shipping_cost") or data.get("delivery_fee") or data.get("delivery"))
    a_spend = parse_float(data.get("ad_spend") or data.get("ads"))
    cat = str(data.get("category") or "כללי")

    city_val = str(data.get("customer_city") or data.get("city") or data.get("notes") or "-")
    if not city_val.strip():
        city_val = "-"

    net_profit = s_price - (c_price + d_fee + a_spend)
    margin = (net_profit / s_price * 100) if s_price > 0 else 0.0

    sale_record = {
        "timestamp": now_str,
        "channel": channel_heb,
        "product_name": prod_name,
        "item_name": prod_name,
        "product": prod_name,
        "category": cat,
        "cost_price": c_price,
        "cost": c_price,
        "delivery_fee": d_fee,
        "shipping_cost": d_fee,
        "selling_price": s_price,
        "sale_price": s_price,
        "ad_spend": a_spend,
        "margin": margin,
        "net_profit": net_profit,
        "payment_method": str(data.get("payment_method", "-")),
        "city": city_val,
        "customer_city": city_val,
        "notes": city_val,
        "campaign_tag": str(data.get("campaign_tag", "none"))
    }

    sale_id = insert_sale(sale_record)
    sale_record["id"] = sale_id
    sale_record["month"] = now_str[:7]

    try:
        append_sale_to_sheet(sale_record)
    except Exception as e:
        print(f"Sheet append error: {e}")

    return {"status": "success", "sale_id": sale_id}

@app.get("/api/analytics")
def get_analytics_data(period: str = None, start_date: str = None, end_date: str = None, user: str = Depends(authenticate)):
    return get_analytics(period=period, start_date=start_date, end_date=end_date)

@app.post("/api/test-telegram")
def test_telegram(user: str = Depends(authenticate)):
    send_telegram_monthly_report()
    return {"status": "Report sent"}

@app.post("/api/reset")
def reset_system(user: str = Depends(authenticate)):
    conn = sqlite3.connect("retail_sales.db", timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("DELETE FROM sales;")
    conn.commit()
    conn.close()

    try:
        client = get_sheets_client()
        if client:
            sheet = client.open(SPREADSHEET_NAME).sheet1
            sheet.clear()
            sheet.append_row(SHEET_HEADERS)
    except Exception as e:
        print(f"Sheet reset error: {e}")

    return {"status": "success", "message": "All data cleared successfully"}
