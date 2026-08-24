# Retail Intelligence Platform

A lightweight point-of-sale (POS) and sales tracking system designed for small retail stores and online deliveries. Built to simplify on-the-floor logging, track profit margins, and sync data between SQLite, Google Sheets, and Telegram.

---

## What It Does

* **Quick Mobile POS:** Fast, lightweight web forms designed for mobile use (or NFC tag shortcuts) to record physical store sales and online deliveries in seconds.
* **Database & Google Sheets Sync:** Stores transactions locally in SQLite and automatically appends rows to a Google Sheets master spreadsheet for bookkeeping.
* **Analytics Dashboard:** Password-protected dashboard showing revenue, costs (COGS + shipping), net profit, and ad spend (ROAS) across custom months or quarters.
* **Automated Telegram Reports:** Scheduled background task (via APScheduler) that sends monthly profit and sales summaries directly to a Telegram group/chat.

---

## Tech Stack

* **Backend:** Python, FastAPI, Uvicorn
* **Database:** SQLite
* **Integrations:** Google Sheets API (`gspread`), Telegram Bot API
* **Scheduler:** APScheduler
* **Frontend:** HTML5, CSS3, Vanilla JavaScript

---

## Architecture Flow

```text
Store / Mobile Device ──► FastAPI Server ──► SQLite (Local DB)
                              │
                              ├──► Google Sheets API (Backup / Bookkeeping)
                              ├──► Analytics Engine (Profit / ROAS)
                              └──► Telegram Bot (Monthly Summaries)
