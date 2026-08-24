import os
import requests
import analytics_engine

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# רשימת מזהי צ'אט מופרדת בפסיקים דרך משתנה סביבה
TELEGRAM_CHAT_IDS = [cid.strip() for cid in os.getenv("TELEGRAM_CHAT_IDS", "").split(",") if cid.strip()]

def format_telegram_report(target_month: str = None) -> str:
    data = analytics_engine.generate_analytics_report(target_month)
    summary = data["summary"]
    period = data["period"]

    msg = f"<b>Business Performance Report - Retail Engine</b>\n"
    msg += f"Period: {period}\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━\n\n"

    msg += f"Net Profit: {summary['net_profit']:,.0f} ILS\n"
    msg += f"Total Revenue: {summary['revenue']:,.0f} ILS\n"
    msg += f"COGS & Shipping: {(summary['cogs'] + summary['shipping']):,.0f} ILS\n"
    msg += f"Margin: {summary['margin_pct']}%\n"
    msg += f"Total Orders: {summary['total_orders']}\n\n"

    msg += f"<b>Channel Breakdown:</b>\n"
    for ch in data["channel_comparison"]:
        msg += f"• {ch['name']}: {ch['profit']:,.0f} ILS ({ch['orders']} orders | {ch['margin_pct']}% margin)\n"

    if data.get("ai_directives"):
        msg += f"\n<b>Strategic Highlights:</b>\n"
        for directive in data["ai_directives"][:3]:
            clean = directive.replace("**", "")
            msg += f"• {clean}\n\n"

    dashboard_url = os.getenv("DASHBOARD_URL", "https://smart-retail-engine.onrender.com/dashboard")
    msg += f"<a href='{dashboard_url}'>View Dashboard</a>"
    return msg

def send_telegram_report(target_month: str = None) -> dict:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_IDS:
        return {"success": False, "error": "Missing bot credentials or recipients"}

    text = format_telegram_report(target_month)
    delivery_status = []

    for chat_id in TELEGRAM_CHAT_IDS:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        try:
            res = requests.post(url, json=payload, timeout=15)
            res_data = res.json()
            if res.status_code == 200 and res_data.get("ok"):
                delivery_status.append({"id": chat_id, "status": "Delivered successfully"})
            else:
                desc = res_data.get("description", res.text)
                delivery_status.append({"id": chat_id, "status": f"Failed ({desc})"})
        except Exception as e:
            delivery_status.append({"id": chat_id, "status": f"Network Error ({str(e)})"})

    return {"success": True, "details": delivery_status}