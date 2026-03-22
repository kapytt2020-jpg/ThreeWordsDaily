"""
data/google_sheets.py — Google Sheets integration for VoodooBot

Syncs user stats to Google Sheets (free, no billing needed).
Uses Service Account credentials (gspread library).

SETUP (one-time, ~5 min):
  1. Go to: https://console.cloud.google.com
  2. Create project "VoodooBot"
  3. Enable "Google Sheets API" + "Google Drive API"
  4. IAM & Admin → Service Accounts → Create Service Account
  5. Name: "voodoo-bot", Role: Editor
  6. Keys → Add Key → JSON → Download
  7. Save as: /Users/usernew/Desktop/VoodooBot/data/google_credentials.json
  8. Create a Google Sheet at sheets.google.com
  9. Share the sheet with the service account email (from the JSON file, "client_email")
  10. Copy the Sheet ID from the URL and set USERS_SHEET_ID in .env

Then run: python3 data/google_sheets.py --sync
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path

log = logging.getLogger("google_sheets")

CREDS_FILE = Path(__file__).parent / "google_credentials.json"
DB_PATH    = os.getenv("DB_PATH", str(Path(__file__).parent.parent / "database" / "voodoo.db"))
SHEET_ID   = os.getenv("USERS_SHEET_ID", "")


def _get_client():
    """Get authenticated gspread client."""
    if not CREDS_FILE.exists():
        raise FileNotFoundError(
            f"Google credentials not found at {CREDS_FILE}\n"
            "See setup instructions at top of this file."
        )
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        scopes = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_file(str(CREDS_FILE), scopes=scopes)
        return gspread.authorize(creds)
    except ImportError:
        raise ImportError("Run: pip install gspread google-auth")


def sync_users_to_sheet(sheet_id: str = None) -> int:
    """Sync all users from SQLite to Google Sheets. Returns count synced."""
    sid = sheet_id or SHEET_ID
    if not sid:
        raise ValueError("USERS_SHEET_ID not set in .env")

    gc = _get_client()
    sh = gc.open_by_key(sid)

    try:
        ws = sh.worksheet("Users")
    except Exception:
        ws = sh.add_worksheet("Users", rows=1000, cols=20)

    # Fetch users from DB
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.execute("""
        SELECT tg_id, first_name, username, level, xp, streak,
               total_lessons, referral_count, created_at
        FROM users ORDER BY xp DESC
    """)
    users = [dict(r) for r in cur.fetchall()]
    con.close()

    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    # Build rows
    header = ["#", "TG ID", "Name", "Username", "Level", "XP", "Streak",
              "Lessons", "Referrals", "Registered", "Last sync"]
    rows = [header]
    for i, u in enumerate(users, 1):
        rows.append([
            i,
            u["tg_id"],
            u["first_name"] or "—",
            f"@{u['username']}" if u["username"] else "—",
            u["level"] or "A2",
            u["xp"] or 0,
            u["streak"] or 0,
            u["total_lessons"] or 0,
            u.get("referral_count") or 0,
            u["created_at"] or "—",
            now,
        ])

    ws.clear()
    ws.update("A1", rows)

    # Format header row
    ws.format("A1:K1", {
        "backgroundColor": {"red": 0.48, "green": 0.23, "blue": 0.93},
        "textFormat": {"foregroundColor": {"red": 1, "green": 1, "blue": 1}, "bold": True},
    })

    log.info("Synced %d users to Google Sheets", len(users))
    return len(users)


def sync_words_to_sheet(sheet_id: str = None) -> int:
    """Sync word database to Google Sheets."""
    sid = sheet_id or SHEET_ID
    if not sid:
        raise ValueError("USERS_SHEET_ID not set in .env")

    gc = _get_client()
    sh = gc.open_by_key(sid)

    try:
        ws = sh.worksheet("Words")
    except Exception:
        ws = sh.add_worksheet("Words", rows=2000, cols=10)

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.execute("SELECT word, translation, level, theme, example_en FROM words ORDER BY level, theme")
    words = [dict(r) for r in cur.fetchall()]
    con.close()

    header = ["Word (EN)", "Translation (UA)", "Level", "Theme", "Example"]
    rows = [header] + [[w["word"], w["translation"], w["level"], w["theme"], w["example_en"]] for w in words]

    ws.clear()
    ws.update("A1", rows)
    log.info("Synced %d words to Google Sheets", len(words))
    return len(words)


def create_dashboard(sheet_id: str = None) -> None:
    """Create/update a Dashboard sheet with key metrics."""
    sid = sheet_id or SHEET_ID
    if not sid:
        return

    gc = _get_client()
    sh = gc.open_by_key(sid)

    try:
        ws = sh.worksheet("Dashboard")
    except Exception:
        ws = sh.add_worksheet("Dashboard", rows=30, cols=5)

    con = sqlite3.connect(DB_PATH)
    total = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    active = con.execute("SELECT COUNT(*) FROM users WHERE streak > 0").fetchone()[0]
    total_xp = con.execute("SELECT SUM(xp) FROM users").fetchone()[0] or 0
    words = con.execute("SELECT COUNT(*) FROM words").fetchone()[0]
    con.close()

    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    data = [
        ["📊 VOODOO DASHBOARD", "", "Updated:", now],
        [""],
        ["Metric", "Value"],
        ["Total Users", total],
        ["Active (streak > 0)", active],
        ["Total XP earned", total_xp],
        ["Words in DB", words],
        ["Avg XP per user", round(total_xp / max(total, 1), 1)],
    ]

    ws.clear()
    ws.update("A1", data)
    log.info("Dashboard updated")


async def scheduled_sync() -> None:
    """Run sync in executor (non-blocking)."""
    loop = asyncio.get_event_loop()
    try:
        count = await loop.run_in_executor(None, sync_users_to_sheet)
        await loop.run_in_executor(None, create_dashboard)
        log.info("Google Sheets sync done: %d users", count)
    except FileNotFoundError:
        log.debug("Google credentials not configured — skipping sync")
    except Exception as e:
        log.error("Google Sheets sync failed: %s", e)


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if "--setup" in sys.argv:
        print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Google Sheets Setup (безкоштовно, ~5 хв)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Відкрий: https://console.cloud.google.com
2. Новий проект → назви "VoodooBot"
3. APIs & Services → Enable APIs:
   • Google Sheets API
   • Google Drive API
4. IAM & Admin → Service Accounts → + Create:
   • Name: voodoo-sheets
   • Role: Editor
5. Клікни на сервіс-акаунт → Keys → Add Key → JSON
6. Збережи файл як:
   /Users/usernew/Desktop/VoodooBot/data/google_credentials.json
7. Відкрий: https://sheets.new
8. Поділися таблицею з email зі step 5 (client_email з JSON)
9. Скопіюй ID таблиці з URL (між /d/ та /edit)
10. Встав в .env: USERS_SHEET_ID=<id>

Потім запусти: python3 data/google_sheets.py --sync
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    elif "--sync" in sys.argv:
        try:
            n = sync_users_to_sheet()
            sync_words_to_sheet()
            create_dashboard()
            print(f"✅ Synced {n} users to Google Sheets")
        except Exception as e:
            print(f"❌ Error: {e}")
            print("\nRun: python3 data/google_sheets.py --setup")
    else:
        print("Usage: python3 data/google_sheets.py [--setup | --sync]")
