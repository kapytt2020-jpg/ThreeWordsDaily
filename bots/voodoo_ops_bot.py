"""
bots/voodoo_ops_bot.py — VoodooOpsBot

Main internal operations/admin brain.
Approval center, deployment, service management, analytics summary,
emergency actions, and agent task delegation.

ALL critical platform actions require OpsBot approval.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    filters,
)

from database import db
from agents import run_agent, spawn_subagent_async, ANALYST_SYSTEM, OPS_SYSTEM
from agents.tools import SERVICES
from agents.group_poster import ops_report, alert, deploy_report

load_dotenv()

logging.basicConfig(
    format="%(asctime)s [ops_bot] %(levelname)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("ops_bot")

TOKEN    = os.getenv("VOODOO_OPS_BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
BOT_DIR  = Path(__file__).parent

LOG_FILES = {
    "voodoo_bot":    "logs/voodoo_bot.log",
    "speak_bot":     "logs/speak_bot.log",
    "teacher_bot":   "logs/teacher_bot.log",
    "publisher_bot": "logs/publisher_bot.log",
    "analyst_bot":   "logs/analyst_bot.log",
    "growth_bot":    "logs/growth_bot.log",
    "miniapp":       "logs/miniapp.log",
    "ops_bot":       "logs/ops_bot.log",
}

if not TOKEN:
    raise RuntimeError("VOODOO_OPS_BOT_TOKEN not set")


def _is_admin(update: Update) -> bool:
    return (update.effective_user is not None and
            update.effective_user.id == ADMIN_ID)


def _proc_running(keyword: str) -> bool:
    r = subprocess.run(["pgrep", "-f", keyword], capture_output=True)
    return r.returncode == 0


# ── Commands ──────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    await update.message.reply_html(
        "🎛 <b>VoodooOpsBot — Command Center</b>\n\n"
        "<b>📊 Аналітика:</b>\n"
        "/dashboard — повний дашборд\n"
        "/stats — швидка статистика\n"
        "/top — топ-10 гравців\n"
        "/retention — DAU/WAU/MAU\n\n"
        "<b>🖥 Сервіси:</b>\n"
        "/status — статус всіх ботів\n"
        "/restart [сервіс|all] — перезапуск\n"
        "/logs [сервіс] — логи\n"
        "/killport — звільнити порт 8000\n\n"
        "<b>✅ Апрували:</b>\n"
        "/approvals — черга апрувів\n\n"
        "<b>🤖 Агенти:</b>\n"
        "/analyze — AI аналіз платформи\n"
        "/plan — планування тижня\n"
        "/improve — ідеї покращення\n\n"
        "<b>⚙️ Управління:</b>\n"
        "/raffle [N] — розіграш\n"
        "/users — список юзерів\n"
        "/broadcast [текст] — розсилка (ОБЕРЕЖНо)\n"
    )


async def cmd_dashboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    stats = await db.get_stats()
    if not stats:
        await update.message.reply_text("⚠️ Дані недоступні.")
        return

    total   = stats["total_users"] or 1
    dau     = stats["active_today"]
    wau     = stats["active_week"]
    mau     = stats["active_month"]
    new_w   = stats["new_week"]
    trend   = "📈" if dau >= 0 else "📉"
    stick   = round(dau / max(mau, 1) * 100, 1)

    # Service status
    svc_lines = []
    for name, (_, kw) in SERVICES.items():
        icon = "✅" if _proc_running(kw) else "❌"
        svc_lines.append(f"{icon} {name}")

    # Approval queue
    conn = db._connect()
    pending_approvals = conn.execute(
        "SELECT COUNT(*) FROM approvals WHERE status='pending'"
    ).fetchone()[0]
    conn.close()

    await update.message.reply_html(
        f"🎛 <b>Voodoo Dashboard — {datetime.now().strftime('%d.%m %H:%M')}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 <b>Юзери</b>\n"
        f"  Всього: <b>{total}</b> | +{new_w} за тиждень\n"
        f"  DAU: <b>{dau}</b>  WAU: <b>{wau}</b>  MAU: <b>{mau}</b> {trend}\n"
        f"  Stickiness: <b>{stick}%</b>\n\n"
        f"⭐ Сер. XP: {stats['avg_xp']}  🔥 Сер. стрік: {stats['avg_streak']}д\n\n"
        f"🖥 <b>Сервіси ({len(SERVICES)})</b>\n"
        + "  ".join(svc_lines[:4]) + "\n"
        + "  ".join(svc_lines[4:]) + "\n\n"
        f"⏳ Апрувів в черзі: <b>{pending_approvals}</b>\n\n"
        f"<i>/analyze — AI аналіз | /approvals — черга</i>"
    )


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    lines = ["🖥 <b>Статус сервісів Voodoo</b>\n"]
    for name, (_, kw) in SERVICES.items():
        icon = "✅" if _proc_running(kw) else "❌"
        lines.append(f"{icon} <code>{name}</code>")
    port_r = subprocess.run(["lsof", "-ti", ":8000"], capture_output=True, text=True)
    pid = port_r.stdout.strip()
    lines.append(f"\n🔌 Port 8000: {'PID ' + pid if pid else 'вільний'}")
    lines.append(f"🕐 {datetime.now().strftime('%H:%M:%S')}")
    await update.message.reply_html("\n".join(lines))


async def cmd_restart(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    args = ctx.args
    if not args:
        svc_list = "\n".join(f"  /restart {n}" for n in SERVICES)
        await update.message.reply_html(
            f"⚙️ Вкажи сервіс:\n{svc_list}\n  /restart all"
        )
        return

    target = args[0].lower()

    # Require confirmation for destructive actions
    if target == "all":
        await update.message.reply_html(
            "⚠️ <b>Перезапуск ВСІХ сервісів</b>\n\nПідтвердь:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Так, перезапустити", callback_data="restart_confirm_all"),
                InlineKeyboardButton("❌ Скасувати", callback_data="restart_cancel"),
            ]]),
        )
        return

    if target not in SERVICES:
        await update.message.reply_text(f"❓ Невідомий сервіс: {target}")
        return

    await update.message.reply_html(
        f"⚠️ Перезапустити <b>{target}</b>?",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Так", callback_data=f"restart_confirm_{target}"),
            InlineKeyboardButton("❌ Ні", callback_data="restart_cancel"),
        ]]),
    )


async def cb_restart(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not _is_admin(update):
        await query.answer("Access denied")
        return
    await query.answer()

    data = query.data
    if data == "restart_cancel":
        await query.edit_message_text("❌ Скасовано.")
        return

    target = data.replace("restart_confirm_", "")

    if target == "all":
        results = []
        for name, (label, kw) in SERVICES.items():
            if name == "ops_bot":
                continue
            try:
                subprocess.run(
                    ["/bin/launchctl", "kickstart", "-k",
                     f"gui/{os.getuid()}/{label}"],
                    capture_output=True, timeout=15
                )
                results.append(f"✅ {name}")
            except Exception as e:
                results.append(f"❌ {name}: {e}")
        await query.edit_message_text("Результати:\n" + "\n".join(results))
        await db.log_ops("ops_bot", "restart_all", "all", str(results))
        return

    svc = SERVICES.get(target)
    if not svc:
        await query.edit_message_text(f"❓ Невідомий: {target}")
        return

    label = svc[0]
    try:
        subprocess.run(
            ["/bin/launchctl", "kickstart", "-k", f"gui/{os.getuid()}/{label}"],
            capture_output=True, timeout=15
        )
        time.sleep(2)
        running = _proc_running(svc[1])
        msg = f"✅ {target} перезапущено" if running else f"⚠️ {target}: процес не знайдено"
    except Exception as e:
        msg = f"❌ {target}: {e}"

    await query.edit_message_text(msg)
    await db.log_ops("ops_bot", "restart", target, msg)
    await deploy_report(f"🔄 <b>Restart: {target}</b>\n{msg}")


async def cmd_logs(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    args = ctx.args
    if not args or args[0] not in LOG_FILES:
        await update.message.reply_html(
            "📋 Використання: <code>/logs [сервіс]</code>\n"
            "Сервіси: " + ", ".join(LOG_FILES.keys())
        )
        return
    name = args[0]
    log_path = Path(__file__).parent.parent / LOG_FILES[name]
    if not log_path.exists():
        await update.message.reply_text(f"❌ Лог не знайдено: {log_path}")
        return
    lines = log_path.read_text(errors="replace").splitlines()
    tail  = "\n".join(lines[-40:])
    if len(tail) > 3800:
        tail = "..." + tail[-3800:]
    await update.message.reply_html(
        f"📋 <b>{name}</b>\n\n<pre>{tail}</pre>"
    )


async def cmd_approvals(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    conn = db._connect()
    rows = conn.execute(
        "SELECT * FROM approvals WHERE status='pending' ORDER BY created_at DESC LIMIT 10"
    ).fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("✅ Черга апрувів порожня.")
        return

    for row in rows:
        r = dict(row)
        payload = json.loads(r.get("payload", "{}"))
        await update.message.reply_html(
            f"📋 <b>Апрув #{r['id']}</b>\n"
            f"Від: {r['request_by']}\n"
            f"Тип: {r['action_type']}\n"
            f"Payload: <code>{json.dumps(payload, ensure_ascii=False)[:200]}</code>\n"
            f"Час: {r['created_at']}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Схвалити", callback_data=f"approve_{r['id']}"),
                InlineKeyboardButton("❌ Відхилити", callback_data=f"reject_{r['id']}"),
            ]]),
        )


async def cb_approval(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not _is_admin(update):
        await query.answer("Access denied")
        return
    await query.answer()
    action, approval_id = query.data.split("_", 1)
    status = "approved" if action == "approve" else "rejected"
    conn = db._connect()
    conn.execute(
        "UPDATE approvals SET status=?, reviewed_by=?, reviewed_at=? WHERE id=?",
        (status, "admin", datetime.now().isoformat(), int(approval_id))
    )
    conn.commit()
    conn.close()
    await query.edit_message_text(
        f"{'✅ Схвалено' if status == 'approved' else '❌ Відхилено'} (ID: {approval_id})"
    )
    await db.log_ops("ops_bot", f"approval_{status}", approval_id)


async def cmd_analyze(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    msg = await update.message.reply_text("🤖 Запускаю AI аналіз платформи...")
    stats = await db.get_stats()

    result = await spawn_subagent_async(
        "analyst",
        ANALYST_SYSTEM,
        f"Проаналізуй стан платформи Voodoo.\n\nДані:\n{json.dumps(stats, ensure_ascii=False)}\n\n"
        "Дай: 1) Загальний стан 2) Топ-3 проблеми 3) Топ-3 можливості 4) Дії на тиждень",
    )
    await msg.edit_text(
        f"🤖 <b>AI Аналіз Voodoo</b>\n\n{result.output}",
        parse_mode="HTML",
    )


async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    stats = await db.get_stats()
    top = "\n".join(
        f"  {i+1}. {u.get('first_name','?')} — {u.get('xp',0)} XP"
        for i, u in enumerate(stats.get("top10", [])[:5])
    )
    await update.message.reply_html(
        f"📊 <b>Voodoo Stats</b>\n\n"
        f"👥 Юзерів: <b>{stats['total_users']}</b>\n"
        f"✅ Активних сьогодні: <b>{stats['active_today']}</b>\n"
        f"📅 За тиждень: <b>{stats['active_week']}</b>\n"
        f"🆕 Нових сьогодні: <b>{stats['new_today']}</b>\n\n"
        f"🏆 ТОП-5:\n{top}"
    )


async def cmd_users(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    conn = db._connect()
    users = conn.execute(
        "SELECT tg_id, first_name, username, xp, streak, last_lesson_date "
        "FROM users ORDER BY xp DESC LIMIT 30"
    ).fetchall()
    conn.close()

    lines = [f"👥 <b>Юзери ({len(users)}+)</b>\n"]
    for i, u in enumerate(users, 1):
        un = f"@{u[2]}" if u[2] else "—"
        lines.append(f"{i}. <code>{u[0]}</code> {u[1]} {un} | {u[3]}XP 🔥{u[4]}")

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "\n..."
    await update.message.reply_html(text)


async def cmd_killport(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    r = subprocess.run(["lsof", "-ti", ":8000"], capture_output=True, text=True)
    pids = r.stdout.strip().split()
    killed = []
    for pid in pids:
        if pid.isdigit():
            subprocess.run(["kill", "-9", pid], capture_output=True)
            killed.append(pid)
    msg = f"✅ Killed PIDs on :8000: {killed}" if killed else "Port 8000 вільний"
    await update.message.reply_text(msg)
    await db.log_ops("ops_bot", "killport", "8000", msg)


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    db.init_db()
    app = Application.builder().token(TOKEN).build()

    admin_filter = filters.User(user_id=ADMIN_ID)

    app.add_handler(CommandHandler("start",     cmd_start,    filters=admin_filter))
    app.add_handler(CommandHandler("dashboard", cmd_dashboard, filters=admin_filter))
    app.add_handler(CommandHandler("status",    cmd_status,   filters=admin_filter))
    app.add_handler(CommandHandler("restart",   cmd_restart,  filters=admin_filter))
    app.add_handler(CommandHandler("logs",      cmd_logs,     filters=admin_filter))
    app.add_handler(CommandHandler("approvals", cmd_approvals, filters=admin_filter))
    app.add_handler(CommandHandler("analyze",   cmd_analyze,  filters=admin_filter))
    app.add_handler(CommandHandler("stats",     cmd_stats,    filters=admin_filter))
    app.add_handler(CommandHandler("users",     cmd_users,    filters=admin_filter))
    app.add_handler(CommandHandler("killport",  cmd_killport, filters=admin_filter))

    app.add_handler(CallbackQueryHandler(cb_restart,  pattern=r"^restart_"))
    app.add_handler(CallbackQueryHandler(cb_approval, pattern=r"^(approve|reject)_"))

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    log.info("VoodooOpsBot online (admin_id=%d)", ADMIN_ID)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
