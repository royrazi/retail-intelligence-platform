import os
import secrets
from fastapi import FastAPI, HTTPException, Query, Depends, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from typing import Optional
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import database
import sheets_service
import analytics_engine
import telegram_service

database.init_db()

app = FastAPI(title="Smart Retail & Fulfillment Engine")

security = HTTPBasic()
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "secret")

def authenticate_admin(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, ADMIN_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0"
}

app.mount("/static", StaticFiles(directory="static"), name="static")

def monthly_cron_job():
    try:
        now = datetime.now()
        prev_month_str = f"{now.year}-{now.month-1:02d}" if now.month > 1 else f"{now.year-1}-12"
        telegram_service.send_telegram_report(target_month=prev_month_str)
    except Exception as e:
        print(f"[Cron Error]: {e}")

scheduler = BackgroundScheduler()
scheduler.add_job(monthly_cron_job, 'cron', day=1, hour=9, minute=0)
scheduler.start()

class SaleCreate(BaseModel):
    channel: str
    item_name: str
    category: Optional[str] = None
    sale_price: float
    cost_price: float = 250.0
    shipping_cost: float = 0.0
    payment_method: Optional[str] = "bit"
    customer_city: Optional[str] = ""
    campaign_tag: Optional[str] = "none"

class CampaignSpendCreate(BaseModel):
    month: str
    campaign_name: str
    spend: float
    notes: Optional[str] = ""

@app.get("/online")
def get_online_ui():
    return FileResponse("static/online.html", headers=NO_CACHE_HEADERS)

@app.get("/store")
def get_store_ui():
    return FileResponse("static/store.html", headers=NO_CACHE_HEADERS)

@app.get("/dashboard")
def get_dashboard_ui(username: str = Depends(authenticate_admin)):
    return FileResponse("static/dashboard.html", headers=NO_CACHE_HEADERS)

@app.get("/")
def home(username: str = Depends(authenticate_admin)):
    return FileResponse("static/dashboard.html", headers=NO_CACHE_HEADERS)

@app.get("/reset")
def direct_reset_page(username: str = Depends(authenticate_admin)):
    try:
        database.clear_all_sales()
        sheets_service.clear_all_sales_sheet()
        return HTMLResponse(
            """
            <html dir='rtl' style='background:#0b1329; color:white; font-family:sans-serif; text-align:center; padding:50px;'>
                <h1 style='color:#4ade80;'>כל נתוני הבדיקה נמחקו בהצלחה</h1>
                <p style='color:#94a3b8;'>מסד הנתונים ו-Google Sheets אופסו ל-0 עסקאות.</p>
                <br>
                <a href='/dashboard' style='display:inline-block; background:#0284c7; color:white; padding:12px 24px; text-decoration:none; border-radius:8px; font-weight:bold;'>חזור לדאשבורד</a>
            </html>
            """
        )
    except Exception as e:
        return HTMLResponse(f"<h3>Error resetting: {e}</h3>", status_code=500)

@app.get("/api/analytics")
def get_analytics(period: Optional[str] = Query(None), username: str = Depends(authenticate_admin)):
    return analytics_engine.generate_analytics_report(period=period)

@app.post("/api/campaign_spend")
def record_campaign_spend(spend: CampaignSpendCreate, username: str = Depends(authenticate_admin)):
    ok = sheets_service.add_campaign_spend(spend.month, spend.campaign_name, spend.spend, spend.notes)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to log campaign spend")
    return {"success": True}

@app.post("/api/reset_test_data")
def reset_test_data(username: str = Depends(authenticate_admin)):
    try:
        database.clear_all_sales()
        sheets_service.clear_all_sales_sheet()
        return {"success": True, "message": "All test data successfully cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/test-telegram")
@app.post("/api/send_telegram_report")
def trigger_telegram(period: Optional[str] = Query(None), username: str = Depends(authenticate_admin)):
    return telegram_service.send_telegram_report(target_month=period)

@app.post("/api/sales", status_code=201)
def create_sale(sale: SaleCreate):
    try:
        saved_sale = database.insert_sale(sale.dict())
        try:
            sheets_service.append_sale_to_sheets(sale.dict())
        except Exception as s_err:
            print(f"[Sheets Sync Warning]: {s_err}")
        return {"success": True, "data": saved_sale}
    except Exception as e:
        print(f"[Create Sale Error]: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sales")
def get_sales(username: str = Depends(authenticate_admin)):
    return database.fetch_all_sales()