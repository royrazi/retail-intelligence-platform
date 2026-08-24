from datetime import datetime
import database
import sheets_service

def get_campaign_spends_map():
    spend_map = {}
    try:
        sheet = sheets_service.get_sheets_client()
        if sheet:
            worksheet = sheet.worksheet("הוצאות_קמפיינים")
            records = worksheet.get_all_records()
            for r in records:
                month = str(r.get("חודש", "")).strip()
                camp = str(r.get("שם קמפיין", "")).strip().lower()
                spend = float(r.get("תקציב שהושקע (₪)", 0) or 0)
                key = f"{month}_{camp}"
                spend_map[key] = spend_map.get(key, 0.0) + spend
    except Exception as e:
        print(f"[Analytics] Error fetching campaign spend: {e}")
    return spend_map

def filter_sales_by_period(sales: list, period: str):
    if not period or period == "all":
        return sales
    
    if "-Q" in period:
        year, q = period.split("-Q")
        quarter_months = {
            "1": [f"{year}-01", f"{year}-02", f"{year}-03"],
            "2": [f"{year}-04", f"{year}-05", f"{year}-06"],
            "3": [f"{year}-07", f"{year}-08", f"{year}-09"],
            "4": [f"{year}-10", f"{year}-11", f"{year}-12"],
        }
        target_months = quarter_months.get(q, [])
        return [s for s in sales if any(str(s.get("timestamp", "")).startswith(m) for m in target_months)]
    
    return [s for s in sales if str(s.get("timestamp", "")).startswith(period)]

def generate_analytics_report(period: str = None):
    sales = database.fetch_all_sales()
    current_month_str = datetime.now().strftime("%Y-%m")
    active_period = period if period else current_month_str

    if not sales:
        return {
            "period": active_period,
            "summary": {"revenue": 0, "cogs": 0, "shipping": 0, "gross_profit": 0, "ad_spend": 0, "net_profit": 0, "margin_pct": 0, "total_orders": 0},
            "channel_comparison": [],
            "campaign_performance": [],
            "product_matrix": [],
            "ai_directives": ["No transaction data recorded for this period."]
        }

    active_sales = filter_sales_by_period(sales, active_period)
    spend_map = get_campaign_spends_map()

    total_rev = sum(float(s.get("sale_price", 0)) for s in active_sales)
    total_cogs = sum(float(s.get("cost_price", 0)) for s in active_sales)
    total_ship = sum(float(s.get("shipping_cost", 0)) for s in active_sales)
    gross_profit = total_rev - total_cogs - total_ship

    total_ad_spend = 0
    if active_period == "all":
        total_ad_spend = sum(spend_map.values())
    elif "-Q" in active_period:
        year, q = active_period.split("-Q")
        q_months = {"1": ["01","02","03"], "2": ["04","05","06"], "3": ["07","08","09"], "4": ["10","11","12"]}.get(q, [])
        total_ad_spend = sum(v for k, v in spend_map.items() if any(k.startswith(f"{year}-{m}") for m in q_months))
    else:
        total_ad_spend = sum(v for k, v in spend_map.items() if k.startswith(active_period))

    true_net_profit = gross_profit - total_ad_spend
    margin_pct = (true_net_profit / total_rev * 100) if total_rev > 0 else 0

    channels = {
        "online": {"name": "אונליין (משלוחים)", "orders": 0, "rev": 0, "cogs": 0, "ship": 0, "profit": 0},
        "store": {"name": "חנות (אלנבי)", "orders": 0, "rev": 0, "cogs": 0, "ship": 0, "profit": 0}
    }

    for s in active_sales:
        ch = s.get("channel", "store")
        if ch not in channels: ch = "store"
        r = float(s.get("sale_price", 0))
        c = float(s.get("cost_price", 0))
        sh = float(s.get("shipping_cost", 0))
        channels[ch]["orders"] += 1
        channels[ch]["rev"] += r
        channels[ch]["cogs"] += c
        channels[ch]["ship"] += sh
        channels[ch]["profit"] += (r - c - sh)

    channel_list = []
    for k, v in channels.items():
        v["margin_pct"] = round((v["profit"] / v["rev"] * 100), 1) if v["rev"] > 0 else 0
        v["avg_ticket"] = round(v["rev"] / v["orders"], 1) if v["orders"] > 0 else 0
        channel_list.append(v)

    campaigns = {}
    for s in active_sales:
        camp = (s.get("campaign_tag") or "none").strip().lower()
        if camp not in campaigns:
            campaigns[camp] = {"name": camp, "orders": 0, "revenue": 0, "gross_profit": 0}
        r = float(s.get("sale_price", 0))
        c = float(s.get("cost_price", 0))
        sh = float(s.get("shipping_cost", 0))
        campaigns[camp]["orders"] += 1
        campaigns[camp]["revenue"] += r
        campaigns[camp]["gross_profit"] += (r - c - sh)

    campaign_list = []
    for camp_name, data in campaigns.items():
        camp_spend = 0
        if active_period == "all":
            camp_spend = sum(v for k, v in spend_map.items() if k.endswith(f"_{camp_name}"))
        else:
            camp_spend = spend_map.get(f"{active_period}_{camp_name}", 0)

        roas = (data["revenue"] / camp_spend) if camp_spend > 0 else 0
        campaign_list.append({
            "campaign": camp_name,
            "orders": data["orders"],
            "revenue": data["revenue"],
            "gross_profit": data["gross_profit"],
            "ad_spend": camp_spend,
            "roas": round(roas, 2),
            "net_profit": data["gross_profit"] - camp_spend
        })

    prods = {}
    for s in active_sales:
        name = s.get("item_name", "אחר")
        if name not in prods:
            prods[name] = {"name": name, "units": 0, "revenue": 0, "profit": 0}
        r = float(s.get("sale_price", 0))
        c = float(s.get("cost_price", 0))
        sh = float(s.get("shipping_cost", 0))
        prods[name]["units"] += 1
        prods[name]["revenue"] += r
        prods[name]["profit"] += (r - c - sh)

    prod_list = sorted(
        [{"name": k, **v, "margin": round(v["profit"] / v["revenue"] * 100, 1) if v["revenue"] > 0 else 0}
         for k, v in prods.items()],
        key=lambda x: x["profit"],
        reverse=True
    )

    ai_directives = []
    if len(active_sales) == 0:
        ai_directives.append(f"No transaction data found for {active_period}.")
    else:
        onl = channels["online"]
        sto = channels["store"]
        if onl["orders"] > 0 and sto["orders"] > 0:
            diff = sto["margin_pct"] - onl["margin_pct"]
            if diff > 0:
                ai_directives.append(f"Retail Store Margin: Store delivers {sto['margin_pct']}% margin vs {onl['margin_pct']}% Online (+{diff:.1f}% due to logistics).")
            else:
                ai_directives.append(f"Online Channel Efficiency: Online channel maintains a healthy margin of {onl['margin_pct']}%.")

        if prod_list:
            star = prod_list[0]
            ai_directives.append(f"Leading Product: '{star['name']}' leads with {star['profit']:,.0f} ILS profit across {star['units']} units.")

        active_camps = [c for c in campaign_list if c["ad_spend"] > 0]
        for c in active_camps:
            if c["roas"] >= 3.0:
                ai_directives.append(f"Top Campaign ({c['campaign']}): Performing at {c['roas']} ROAS. Scale budget allocation.")
            elif c["roas"] < 1.8:
                ai_directives.append(f"Low Yield Campaign ({c['campaign']}): ROAS at {c['roas']}. Review creative targeting.")

    return {
        "period": active_period,
        "summary": {
            "revenue": total_rev,
            "cogs": total_cogs,
            "shipping": total_ship,
            "gross_profit": gross_profit,
            "ad_spend": total_ad_spend,
            "net_profit": true_net_profit,
            "margin_pct": round(margin_pct, 1),
            "total_orders": len(active_sales)
        },
        "channel_comparison": channel_list,
        "campaign_performance": campaign_list,
        "product_matrix": prod_list,
        "ai_directives": ai_directives
    }