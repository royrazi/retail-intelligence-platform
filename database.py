import sqlite3
from datetime import datetime

DB_NAME = "retail_sales.db"

def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT,
                item_name TEXT,
                category TEXT,
                sale_price REAL,
                cost_price REAL,
                shipping_cost REAL,
                payment_method TEXT,
                customer_city TEXT,
                campaign_tag TEXT,
                timestamp TEXT
            )
        """)
        conn.commit()

def insert_sale(sale_dict: dict):
    init_db()
    current_time = sale_dict.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def _execute_insert(c):
        c.execute("""
            INSERT INTO sales (
                channel, item_name, category, sale_price, 
                cost_price, shipping_cost, payment_method, 
                customer_city, campaign_tag, timestamp
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(sale_dict.get("channel", "store")),
            str(sale_dict.get("item_name", "מוצר כללי")),
            str(sale_dict.get("category", "מזוודות")),
            float(sale_dict.get("sale_price", 0)),
            float(sale_dict.get("cost_price", 250.0)),
            float(sale_dict.get("shipping_cost", 0.0)),
            str(sale_dict.get("payment_method", "bit")),
            str(sale_dict.get("customer_city", "")),
            str(sale_dict.get("campaign_tag", "none")),
            str(current_time)
        ))

    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            _execute_insert(cursor)
            conn.commit()
            return {"id": cursor.lastrowid, "timestamp": current_time, **sale_dict}
        except Exception:
            cursor.execute("DROP TABLE IF EXISTS sales")
            conn.commit()
            init_db()
            _execute_insert(cursor)
            conn.commit()
            return {"id": cursor.lastrowid, "timestamp": current_time, **sale_dict}

def fetch_all_sales():
    init_db()
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sales ORDER BY id DESC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def clear_all_sales():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS sales")
        conn.commit()
    init_db()
    return True