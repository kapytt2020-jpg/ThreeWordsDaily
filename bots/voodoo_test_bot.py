"""
bots/voodoo_test_bot.py — VoodooTesttbot

Internal QA bot. Tests flows, validates commands, runs regression checks.
Reports results to admin.
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, filters

from database import db
from agents.tools import SERVICES

load_dotenv()

logging.basicConfig(
    format="%(asctime)s [test_bot] %(levelname)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("test_bot")

TOKEN    = os.getenv("VOODOO_TEST_BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))

if not TOKEN:
    raise RuntimeError("VOODOO_TEST_BOT_TOKEN not set")


# ── Test runners ──────────────────────────────────────────────────────────────

async def run_service_checks() -> list[dict]:
    results = []
    for name, (label, keyword) in SERVICES.items():
        r = subprocess.run(["pgrep", "-f", keyword], capture_output=True)
        results.append({
            "service": name,
            "status": "✅ running" if r.returncode == 0 else "❌ stopped",
            "ok": r.returncode == 0,
        })
    return results


async def run_db_checks() -> list[dict]:
    results = []
    try:
        stats = await db.get_stats()
        results.append({"test": "DB connection", "ok": True, "detail": f"{stats['total_users']} users"})

        conn = db._connect()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        expected = {"users", "words", "content_plan", "ops_log", "approvals", "agent_tasks"}
        found    = {r[0] for r in tables}
        missing  = expected - found
        conn.close()

        results.append({
            "test": "DB tables",
            "ok": not missing,
            "detail": f"Missing: {missing}" if missing else "All tables present",
        })
    except Exception as e:
        results.append({"test": "DB", "ok": False, "detail": str(e)})
    return results


async def run_env_checks() -> list[dict]:
    required_vars = [
        "VOODOO_BOT_TOKEN", "VOODOO_OPS_BOT_TOKEN", "ADMIN_CHAT_ID",
        "DB_PATH",
    ]
    results = []
    for var in required_vars:
        val = os.getenv(var, "")
        results.append({
            "test": f"ENV:{var}",
            "ok": bool(val),
            "detail": "set" if val else "MISSING",
        })
    return results


# ── Commands ──────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_html(
        "🧪 <b>VoodooTesttbot</b>\n\n"
        "Internal QA bot.\n\n"
        "/test_all — повний тест\n"
        "/test_services — статус сервісів\n"
        "/test_db — перевірка БД\n"
        "/test_env — перевірка .env\n"
        "/health — швидкий health check\n"
    )


async def cmd_test_all(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        return
    msg = await update.message.reply_text("🧪 Запускаю повний тест...")

    svc  = await run_service_checks()
    dbt  = await run_db_checks()
    env  = await run_env_checks()

    all_results = svc + dbt + env
    passed = sum(1 for r in all_results if r.get("ok"))
    total  = len(all_results)
    ok_icon = "✅" if passed == total else "⚠️"

    lines = [f"{ok_icon} <b>Test Report — {datetime.now().strftime('%H:%M:%S')}</b>",
             f"Passed: {passed}/{total}\n"]

    lines.append("<b>Services:</b>")
    for r in svc:
        lines.append(f"  {r['status']} {r['service']}")

    lines.append("\n<b>Database:</b>")
    for r in dbt:
        icon = "✅" if r["ok"] else "❌"
        lines.append(f"  {icon} {r['test']}: {r.get('detail','')}")

    lines.append("\n<b>Environment:</b>")
    for r in env:
        icon = "✅" if r["ok"] else "❌"
        lines.append(f"  {icon} {r['test']}: {r.get('detail','')}")

    await msg.edit_text("\n".join(lines), parse_mode="HTML")


async def cmd_health(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        return
    svc = await run_service_checks()
    running = sum(1 for r in svc if r["ok"])
    total   = len(svc)
    icon    = "✅" if running == total else ("⚠️" if running > 0 else "🔴")
    await update.message.reply_html(
        f"{icon} <b>Health Check</b>\n"
        f"Services: {running}/{total} running\n"
        f"🕐 {datetime.now().strftime('%H:%M:%S')}"
    )


async def main() -> None:
    db.init_db()
    app = Application.builder().token(TOKEN).build()
    admin_f = filters.User(user_id=ADMIN_ID) if ADMIN_ID else filters.ALL

    app.add_handler(CommandHandler("start",         cmd_start,    filters=admin_f))
    app.add_handler(CommandHandler("test_all",      cmd_test_all, filters=admin_f))
    app.add_handler(CommandHandler("test_services", cmd_test_all, filters=admin_f))
    app.add_handler(CommandHandler("test_db",       cmd_test_all, filters=admin_f))
    app.add_handler(CommandHandler("test_env",      cmd_test_all, filters=admin_f))
    app.add_handler(CommandHandler("health",        cmd_health,   filters=admin_f))

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    log.info("VoodooTesttbot online")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
