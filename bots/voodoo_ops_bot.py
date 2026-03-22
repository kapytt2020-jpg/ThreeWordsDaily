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
        "<b>☁️ Хмара:</b>\n"
        "/cloud — статус хмарних серверів\n"
        "/cloudstart [id] — запустити сервер\n"
        "/cloudstop [id] — зупинити сервер\n"
        "/cloudnew — створити новий сервер\n"
        "/failover — ручний failover\n\n"
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


async def cmd_retention(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    stats = await db.get_stats()
    dau = stats["active_today"]
    wau = stats["active_week"]
    mau = stats["active_month"]
    total = stats["total_users"] or 1
    await update.message.reply_html(
        f"📈 <b>Retention — {datetime.now().strftime('%d.%m %H:%M')}</b>\n\n"
        f"DAU: <b>{dau}</b> ({round(dau/total*100,1)}% від бази)\n"
        f"WAU: <b>{wau}</b> ({round(wau/total*100,1)}%)\n"
        f"MAU: <b>{mau}</b> ({round(mau/total*100,1)}%)\n\n"
        f"Stickiness DAU/MAU: <b>{round(dau/max(mau,1)*100,1)}%</b>\n"
        f"Stickiness DAU/WAU: <b>{round(dau/max(wau,1)*100,1)}%</b>\n\n"
        f"Всього юзерів: <b>{total}</b> | +{stats['new_today']} сьогодні | +{stats['new_week']} за тиждень"
    )


async def cmd_top(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    stats = await db.get_stats()
    lines = ["🏆 <b>ТОП-10 гравців</b>\n"]
    medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
    for i, u in enumerate(stats.get("top10", [])[:10]):
        un = f"@{u['username']}" if u.get("username") else u.get("first_name", "?")
        lines.append(f"{medals[i]} {un} — <b>{u['xp']} XP</b> 🔥{u.get('streak',0)}")
    await update.message.reply_html("\n".join(lines))


async def cmd_improve(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    msg = await update.message.reply_text("🤖 Запускаю агента покращення...")
    from agents.base import run_improvement_agent
    asyncio.create_task(run_improvement_agent())
    await msg.edit_text(
        "🤖 <b>Агент покращення запущений</b>\n\n"
        "Агент досліджує GitHub і веб → аналізує кодову базу → "
        "пропонує покращення.\n\n"
        "Результат прийде в групу 🤖 Agent-Talk.",
        parse_mode="HTML",
    )


async def cmd_plan(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    msg = await update.message.reply_text("📅 Генерую план тижня...")
    stats = await db.get_stats()
    result = await spawn_subagent_async(
        "ops",
        OPS_SYSTEM,
        f"Склади детальний план роботи на наступний тиждень для платформи Voodoo English.\n"
        f"Поточні дані: {json.dumps(stats, ensure_ascii=False)}\n\n"
        "Формат: пн-нд по пунктам, з пріоритетами (🔴🟡🟢). "
        "Включи: технічні завдання, контент, зростання, монетизацію.",
    )
    await msg.edit_text(
        f"📅 <b>План тижня Voodoo</b>\n\n{result.output}",
        parse_mode="HTML",
    )


async def cmd_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    if not ctx.args:
        await update.message.reply_html(
            "📢 <b>Broadcast</b>\n\n"
            "Використання: <code>/broadcast Текст повідомлення</code>\n\n"
            "⚠️ Надсилає всім активним юзерам!"
        )
        return
    text = " ".join(ctx.args)
    await update.message.reply_html(
        f"⚠️ <b>Підтверди розсилку</b>\n\n<i>{text[:300]}</i>",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📢 Розіслати", callback_data=f"broadcast_go"),
            InlineKeyboardButton("❌ Скасувати", callback_data="broadcast_cancel"),
        ]]),
    )
    ctx.user_data["broadcast_text"] = text


async def cb_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not _is_admin(update):
        await query.answer("Access denied")
        return
    await query.answer()

    if query.data == "broadcast_cancel":
        await query.edit_message_text("❌ Розсилку скасовано.")
        return

    text = ctx.user_data.get("broadcast_text", "")
    if not text:
        await query.edit_message_text("❌ Текст не знайдено.")
        return

    conn = db._connect()
    user_ids = [r[0] for r in conn.execute("SELECT tg_id FROM users").fetchall()]
    conn.close()

    sent = failed = 0
    bot = query.get_bot()
    for uid in user_ids:
        try:
            await bot.send_message(chat_id=uid, text=text)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1

    result_msg = f"📢 Розсилка завершена\n✅ Надіслано: {sent}\n❌ Помилок: {failed}"
    await query.edit_message_text(result_msg)
    await db.log_ops("ops_bot", "broadcast", "all", result_msg)
    await ops_report(result_msg)


# ── Cloud Server Management ────────────────────────────────────────────────────

CLOUD_PROVIDERS = {
    "hetzner": os.getenv("HETZNER_API_TOKEN", ""),
    "digitalocean": os.getenv("DO_API_TOKEN", ""),
    "vultr": os.getenv("VULTR_API_KEY", ""),
}

HETZNER_API = "https://api.hetzner.cloud/v1"
DO_API      = "https://api.digitalocean.com/v2"


async def _hetzner_get(path: str) -> dict:
    import urllib.request
    token = CLOUD_PROVIDERS["hetzner"]
    if not token:
        return {"error": "HETZNER_API_TOKEN not set"}
    req = urllib.request.Request(
        f"{HETZNER_API}{path}",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            import json as _json
            return _json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


async def _hetzner_post(path: str, payload: dict) -> dict:
    import urllib.request, json as _json
    token = CLOUD_PROVIDERS["hetzner"]
    if not token:
        return {"error": "HETZNER_API_TOKEN not set"}
    data = _json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{HETZNER_API}{path}",
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return _json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


async def _do_get(path: str) -> dict:
    import urllib.request
    token = CLOUD_PROVIDERS["digitalocean"]
    if not token:
        return {"error": "DO_API_TOKEN not set"}
    req = urllib.request.Request(
        f"{DO_API}{path}",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            import json as _json
            return _json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


async def cmd_cloud(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    msg = await update.message.reply_text("☁️ Запитую хмарні провайдери...")

    lines = ["☁️ <b>Хмарні сервери Voodoo</b>\n"]
    any_configured = False

    # Hetzner
    if CLOUD_PROVIDERS["hetzner"]:
        any_configured = True
        data = await _hetzner_get("/servers")
        if "error" in data:
            lines.append(f"🔴 Hetzner: {data['error']}")
        else:
            servers = data.get("servers", [])
            lines.append(f"<b>Hetzner Cloud ({len(servers)} серверів):</b>")
            for s in servers:
                status_icon = "🟢" if s["status"] == "running" else "🔴"
                ip = s.get("public_net", {}).get("ipv4", {}).get("ip", "?")
                lines.append(
                    f"  {status_icon} <code>{s['id']}</code> {s['name']} "
                    f"({s['server_type']['name']}) — {ip} — {s['status']}"
                )

    # DigitalOcean
    if CLOUD_PROVIDERS["digitalocean"]:
        any_configured = True
        data = await _do_get("/droplets")
        if "error" in data:
            lines.append(f"🔴 DigitalOcean: {data['error']}")
        else:
            droplets = data.get("droplets", [])
            lines.append(f"\n<b>DigitalOcean ({len(droplets)} droplets):</b>")
            for d in droplets:
                status_icon = "🟢" if d["status"] == "active" else "🔴"
                ip = d.get("networks", {}).get("v4", [{}])[0].get("ip_address", "?")
                lines.append(
                    f"  {status_icon} <code>{d['id']}</code> {d['name']} "
                    f"({d['size_slug']}) — {ip} — {d['status']}"
                )

    if not any_configured:
        lines.append(
            "⚠️ Жоден хмарний провайдер не налаштований.\n\n"
            "Додай у .env:\n"
            "<code>HETZNER_API_TOKEN=xxx</code>\n"
            "<code>DO_API_TOKEN=xxx</code>\n"
            "<code>VULTR_API_KEY=xxx</code>"
        )

    await msg.edit_text("\n".join(lines), parse_mode="HTML")


async def cmd_cloudstart(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    if not ctx.args:
        await update.message.reply_text("Використання: /cloudstart [server_id]")
        return
    server_id = ctx.args[0]
    msg = await update.message.reply_text(f"▶️ Запускаю сервер {server_id}...")
    result = await _hetzner_post(f"/servers/{server_id}/actions/poweron", {})
    if "error" in result:
        await msg.edit_text(f"❌ Помилка: {result['error']}")
    else:
        action = result.get("action", {})
        await msg.edit_text(
            f"✅ Сервер {server_id} запускається\n"
            f"Action ID: {action.get('id')} | Status: {action.get('status')}"
        )
    await db.log_ops("ops_bot", "cloud_start", server_id, str(result))


async def cmd_cloudstop(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    if not ctx.args:
        await update.message.reply_text("Використання: /cloudstop [server_id]")
        return
    server_id = ctx.args[0]
    await update.message.reply_html(
        f"⚠️ Зупинити сервер <code>{server_id}</code>?",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔴 Зупинити", callback_data=f"cloudstop_confirm_{server_id}"),
            InlineKeyboardButton("❌ Скасувати", callback_data="cloudstop_cancel"),
        ]]),
    )


async def cb_cloudstop(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not _is_admin(update):
        await query.answer("Access denied")
        return
    await query.answer()
    if query.data == "cloudstop_cancel":
        await query.edit_message_text("❌ Скасовано.")
        return
    server_id = query.data.replace("cloudstop_confirm_", "")
    result = await _hetzner_post(f"/servers/{server_id}/actions/poweroff", {})
    if "error" in result:
        await query.edit_message_text(f"❌ Помилка: {result['error']}")
    else:
        action = result.get("action", {})
        await query.edit_message_text(
            f"🔴 Сервер {server_id} зупиняється\n"
            f"Action: {action.get('id')} | Status: {action.get('status')}"
        )
    await db.log_ops("ops_bot", "cloud_stop", server_id, str(result))


async def cmd_cloudnew(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    await update.message.reply_html(
        "🆕 <b>Створити новий сервер</b>\n\n"
        "Вибери конфігурацію:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 CX11 — €3.79/міс (2GB RAM)", callback_data="cloudnew_cx11")],
            [InlineKeyboardButton("⚡ CX21 — €6.49/міс (4GB RAM)", callback_data="cloudnew_cx21")],
            [InlineKeyboardButton("🚀 CX31 — €11.49/міс (8GB RAM)", callback_data="cloudnew_cx31")],
            [InlineKeyboardButton("❌ Скасувати", callback_data="cloudnew_cancel")],
        ]),
    )


async def cb_cloudnew(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not _is_admin(update):
        await query.answer("Access denied")
        return
    await query.answer()

    if query.data == "cloudnew_cancel":
        await query.edit_message_text("❌ Скасовано.")
        return

    server_type = query.data.replace("cloudnew_", "")
    await query.edit_message_text(f"🔄 Створюю сервер {server_type.upper()}...")

    import json as _json
    payload = {
        "name": f"voodoo-{server_type}-{datetime.now().strftime('%m%d-%H%M')}",
        "server_type": server_type,
        "image": "ubuntu-22.04",
        "location": "nbg1",
        "labels": {"project": "voodoo", "auto": "true"},
    }
    result = await _hetzner_post("/servers", payload)

    if "error" in result:
        await query.edit_message_text(f"❌ Помилка: {result['error']}")
        return

    server = result.get("server", {})
    ip = server.get("public_net", {}).get("ipv4", {}).get("ip", "?")
    root_pw = result.get("root_password", "—")

    await query.edit_message_text(
        f"✅ <b>Новий сервер створено!</b>\n\n"
        f"ID: <code>{server.get('id')}</code>\n"
        f"Назва: {server.get('name')}\n"
        f"IP: <code>{ip}</code>\n"
        f"Root pw: <code>{root_pw}</code>\n"
        f"Статус: {server.get('status')}\n\n"
        f"⚠️ Збережи root password — більше не покажу!"
    ,
        parse_mode="HTML"
    )
    await db.log_ops("ops_bot", "cloud_new", server.get("name"), f"ip={ip}")

    # Alert deploy topic
    from agents.group_poster import deploy_report
    await deploy_report(
        f"🆕 <b>Новий сервер</b>\n"
        f"Type: {server_type.upper()} | IP: {ip} | ID: {server.get('id')}"
    )


async def cmd_failover(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    await update.message.reply_html(
        "🔄 <b>Ручний Failover</b>\n\n"
        "Ця команда:\n"
        "1. Перевіряє основний сервер\n"
        "2. Якщо недоступний — запускає резервний\n"
        "3. Якщо обидва впали — створює новий автоматично\n\n"
        "Підтвердити failover?",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Запустити", callback_data="failover_go"),
            InlineKeyboardButton("❌ Скасувати", callback_data="failover_cancel"),
        ]]),
    )


async def cb_failover(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not _is_admin(update):
        await query.answer("Access denied")
        return
    await query.answer()

    if query.data == "failover_cancel":
        await query.edit_message_text("❌ Скасовано.")
        return

    await query.edit_message_text("🔄 Виконую failover...")
    log.info("Manual failover initiated by admin")

    # Get all servers
    data = await _hetzner_get("/servers")
    if "error" in data:
        await query.edit_message_text(f"❌ Не можу отримати список серверів: {data['error']}")
        return

    servers = data.get("servers", [])
    running = [s for s in servers if s["status"] == "running"]
    stopped = [s for s in servers if s["status"] != "running"]

    if running:
        await query.edit_message_text(
            f"✅ <b>Failover не потрібен</b>\n\n"
            f"Активних серверів: {len(running)}\n"
            + "\n".join(f"  🟢 {s['name']} ({s.get('public_net',{}).get('ipv4',{}).get('ip','?')})"
                        for s in running)
        ,
        parse_mode="HTML"
    )
        return

    # Try to start a stopped server
    if stopped:
        server = stopped[0]
        await query.edit_message_text(f"⚡ Запускаю резервний сервер {server['name']}...")
        result = await _hetzner_post(f"/servers/{server['id']}/actions/poweron", {})
        if "error" not in result:
            ip = server.get("public_net", {}).get("ipv4", {}).get("ip", "?")
            await query.edit_message_text(
                f"✅ <b>Failover успішний!</b>\n"
                f"Сервер {server['name']} запускається\nIP: <code>{ip}</code>"
            ,
        parse_mode="HTML"
    )
            await db.log_ops("ops_bot", "failover", server["name"], "started_stopped_server")
            return

    # Last resort: create new server
    await query.edit_message_text("🆕 Усі сервери недоступні. Створюю новий...")
    payload = {
        "name": f"voodoo-failover-{datetime.now().strftime('%m%d-%H%M')}",
        "server_type": "cx11",
        "image": "ubuntu-22.04",
        "location": "nbg1",
        "labels": {"project": "voodoo", "failover": "true"},
    }
    result = await _hetzner_post("/servers", payload)
    if "error" in result:
        await query.edit_message_text(f"❌ Failover failed: {result['error']}\nЗверніться до провайдера вручну!")
        return

    server = result.get("server", {})
    ip = server.get("public_net", {}).get("ipv4", {}).get("ip", "?")
    await query.edit_message_text(
        f"🆕 <b>Новий failover-сервер!</b>\n"
        f"IP: <code>{ip}</code>\nPassword: <code>{result.get('root_password','—')}</code>"
    ,
        parse_mode="HTML"
    )
    await db.log_ops("ops_bot", "failover_new_server", server.get("name"), f"ip={ip}")


async def cmd_raffle(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    import random
    n = int(ctx.args[0]) if ctx.args and ctx.args[0].isdigit() else 1
    conn = db._connect()
    users = conn.execute("SELECT tg_id, first_name, username, xp FROM users ORDER BY xp DESC").fetchall()
    conn.close()
    if not users:
        await update.message.reply_text("Юзерів не знайдено.")
        return
    winners = random.sample(users, min(n, len(users)))
    lines = [f"🎰 <b>Розіграш — {n} переможець(ів)</b>\n"]
    for i, w in enumerate(winners, 1):
        un = f"@{w[2]}" if w[2] else w[1]
        lines.append(f"{i}. {un} (ID: <code>{w[0]}</code>) — {w[3]} XP")
    await update.message.reply_html("\n".join(lines))


# ── SSH / Server helpers ──────────────────────────────────────────────────────

def _load_ssh_ip() -> str:
    state_file = Path(__file__).parent.parent / "deploy" / "vultr_state.json"
    try:
        return json.loads(state_file.read_text()).get("ip", "")
    except Exception:
        return ""

SSH_IP  = _load_ssh_ip()
SSH_KEY = Path.home() / ".ssh" / "voodoo_deploy"

# Patterns that must never be executed remotely
_DESTRUCTIVE_RE = [
    r"rm\s+-[rRf]+\s+/",
    r"dd\s+if=",
    r"mkfs",
    r">\s*/dev/",
    r"shutdown",
    r"halt",
    r"reboot",
    r":()\{",          # fork bomb
]


def _sanitize_cmd(cmd: str) -> str | None:
    """Return None if the command looks destructive, else the cmd itself."""
    import re
    for pat in _DESTRUCTIVE_RE:
        if re.search(pat, cmd):
            return None
    return cmd


def _ssh(cmd: str, timeout: int = 30) -> tuple[str, str, int]:
    """Run a command on the Vultr server. Returns (stdout, stderr, returncode)."""
    if not SSH_IP:
        return "", "SSH_IP not configured (deploy/vultr_state.json missing?)", 1
    r = subprocess.run(
        ["ssh", "-o", "StrictHostKeyChecking=no", "-i", str(SSH_KEY),
         f"root@{SSH_IP}", cmd],
        capture_output=True, text=True, timeout=timeout,
    )
    return r.stdout, r.stderr, r.returncode


# ── New commands ───────────────────────────────────────────────────────────────

PUBLIC_CHANNEL = "@VoodooEnglish"

SERVER_BOTS = [
    "voodoo_bot",
    "voodoo_speak_bot",
    "voodoo_teacher_bot",
    "voodoo_publisher_bot",
    "voodoo_analyst_bot",
    "voodoo_growth_bot",
    "voodoo_ops_bot",
    "voodoo_group_manager",
    "voodoo_content_scheduler",
]


async def cmd_sh(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Run an arbitrary bash command on the Vultr production server."""
    if not _is_admin(update):
        return
    if not ctx.args:
        await update.message.reply_html(
            "Використання: <code>/sh &lt;command&gt;</code>\n"
            "Приклад: <code>/sh uptime</code>"
        )
        return
    raw_cmd = " ".join(ctx.args)
    if _sanitize_cmd(raw_cmd) is None:
        await update.message.reply_html("🚫 <b>Заблоковано:</b> деструктивна команда.")
        return
    msg = await update.message.reply_html("💻 Виконую на сервері...")
    try:
        stdout, stderr, rc = await asyncio.get_event_loop().run_in_executor(
            None, lambda: _ssh(raw_cmd)
        )
    except subprocess.TimeoutExpired:
        await msg.edit_text("⏱ Timeout (30 s)")
        return
    except Exception as e:
        await msg.edit_text(f"❌ SSH error: {e}")
        return

    output = (stdout + stderr).strip()
    if len(output) > 3900:
        output = output[:3900] + "\n…(truncated)"
    if not output:
        output = f"(no output, exit code {rc})"
    await msg.edit_text(
        f"💻 <b>SSH output:</b>\n<code>{output}</code>",
        parse_mode="HTML",
    )


async def cmd_deploy(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/deploy [bot_name] — git pull + systemctl restart on server."""
    if not _is_admin(update):
        return
    bot_arg = ctx.args[0] if ctx.args else None
    if bot_arg:
        restart_cmd = f"systemctl restart {bot_arg}"
        label = bot_arg
    else:
        restart_cmd = "systemctl restart " + " ".join(SERVER_BOTS)
        label = "all bots"

    msg = await update.message.reply_html(
        f"🚀 Deploying <b>{label}</b>…"
    )
    full_cmd = f"cd /opt/voodoo && git pull origin voodoo && {restart_cmd}"
    try:
        stdout, stderr, rc = await asyncio.get_event_loop().run_in_executor(
            None, lambda: _ssh(full_cmd, timeout=60)
        )
    except subprocess.TimeoutExpired:
        await msg.edit_text("⏱ Deploy timeout (60 s)")
        return
    except Exception as e:
        await msg.edit_text(f"❌ SSH error: {e}")
        return

    output = (stdout + stderr).strip()
    if len(output) > 3500:
        output = "..." + output[-3500:]
    icon = "✅" if rc == 0 else "❌"
    await msg.edit_text(
        f"{icon} <b>Deploy {label}</b>\n<code>{output or 'OK'}</code>",
        parse_mode="HTML",
    )
    await deploy_report(f"{icon} Deploy <b>{label}</b> — rc={rc}")


async def cmd_serverlogs(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/serverlogs [bot] [n] — tail error log from /opt/voodoo/logs/."""
    if not _is_admin(update):
        return
    args = ctx.args or []
    bot_name = args[0] if args else "voodoo_bot"
    n = 20
    if len(args) >= 2 and args[1].isdigit():
        n = int(args[1])
    log_path = f"/opt/voodoo/logs/{bot_name}_error.log"
    cmd = f"tail -n {n} {log_path} 2>&1"
    msg = await update.message.reply_html(
        f"📋 Отримую <code>{log_path}</code> ({n} рядків)…"
    )
    try:
        stdout, stderr, rc = await asyncio.get_event_loop().run_in_executor(
            None, lambda: _ssh(cmd)
        )
    except Exception as e:
        await msg.edit_text(f"❌ SSH error: {e}")
        return
    output = (stdout + stderr).strip()
    if len(output) > 3800:
        output = "..." + output[-3800:]
    if not output:
        output = "(лог порожній або файл не існує)"
    await msg.edit_text(
        f"📋 <b>{bot_name} error log</b>\n<pre>{output}</pre>",
        parse_mode="HTML",
    )


async def cmd_srvstatus(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/srvstatus — systemctl status + uptime/free/df on Vultr server."""
    if not _is_admin(update):
        return
    bots_str = " ".join(SERVER_BOTS)
    cmd = (
        f"systemctl is-active {bots_str} ; "
        "echo '---' ; uptime && free -m && df -h /opt/voodoo"
    )
    msg = await update.message.reply_html("🖥 Запитую сервер…")
    try:
        stdout, stderr, rc = await asyncio.get_event_loop().run_in_executor(
            None, lambda: _ssh(cmd)
        )
    except Exception as e:
        await msg.edit_text(f"❌ SSH error: {e}")
        return
    output = (stdout + stderr).strip()
    if len(output) > 3800:
        output = "..." + output[-3800:]
    await msg.edit_text(
        f"🖥 <b>Server status ({SSH_IP})</b>\n<pre>{output}</pre>",
        parse_mode="HTML",
    )


async def cmd_srvrestart(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/srvrestart <bot> — restart a systemd service on the Vultr server."""
    if not _is_admin(update):
        return
    if not ctx.args:
        await update.message.reply_html(
            "Використання: <code>/srvrestart &lt;bot_name&gt;</code>\n"
            "Наприклад: <code>/srvrestart voodoo_bot</code>"
        )
        return
    svc = ctx.args[0]
    await update.message.reply_html(
        f"⚠️ Перезапустити <b>{svc}</b> на сервері?",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Так", callback_data=f"srvrestart_confirm_{svc}"),
            InlineKeyboardButton("❌ Ні",  callback_data="srvrestart_cancel"),
        ]]),
    )


async def cb_srvrestart(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not _is_admin(update):
        await query.answer("Access denied")
        return
    await query.answer()
    if query.data == "srvrestart_cancel":
        await query.edit_message_text("❌ Скасовано.")
        return
    svc = query.data.replace("srvrestart_confirm_", "")
    try:
        stdout, stderr, rc = await asyncio.get_event_loop().run_in_executor(
            None, lambda: _ssh(f"systemctl restart {svc}")
        )
    except Exception as e:
        await query.edit_message_text(f"❌ SSH error: {e}")
        return
    icon = "✅" if rc == 0 else "❌"
    output = (stdout + stderr).strip() or "OK"
    await query.edit_message_text(
        f"{icon} <b>srvrestart {svc}</b>\n<code>{output}</code>",
        parse_mode="HTML",
    )
    await deploy_report(f"{icon} Server restart <b>{svc}</b> — rc={rc}")


async def cmd_public(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/public <text> — post text to @VoodooEnglish public channel."""
    if not _is_admin(update):
        return
    if not ctx.args:
        await update.message.reply_html(
            "Використання: <code>/public Текст повідомлення</code>"
        )
        return
    text = " ".join(ctx.args)
    pub_token = os.getenv("VOODOO_PUBLISHER_BOT_TOKEN") or TOKEN
    try:
        import urllib.request
        payload = json.dumps({"chat_id": PUBLIC_CHANNEL, "text": text}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{pub_token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            result = json.loads(r.read())
        if result.get("ok"):
            await update.message.reply_html(
                f"✅ Опубліковано в {PUBLIC_CHANNEL}:\n<i>{text[:200]}</i>"
            )
        else:
            await update.message.reply_html(
                f"❌ Telegram error: {result.get('description', '?')}"
            )
    except Exception as e:
        await update.message.reply_html(f"❌ Помилка: {e}")


async def cmd_env(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/env [KEY] — show .env keys with masked values."""
    if not _is_admin(update):
        return
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        await update.message.reply_html("❌ .env файл не знайдено.")
        return

    lines_raw = env_path.read_text(errors="replace").splitlines()

    def _mask(line: str) -> str:
        if "=" not in line or line.strip().startswith("#"):
            return line
        key, _, val = line.partition("=")
        preview = val[:3] if val else ""
        return f"{key}={preview}{'*' * max(0, len(val) - 3)}"

    key_filter = ctx.args[0].upper() if ctx.args else None
    if key_filter:
        matched = [_mask(l) for l in lines_raw if l.startswith(key_filter + "=")]
        if matched:
            await update.message.reply_html(
                f"🔑 <code>{'<br>'.join(matched)}</code>"
            )
        else:
            await update.message.reply_html(f"❌ Ключ <code>{key_filter}</code> не знайдено.")
        return

    masked = "\n".join(_mask(l) for l in lines_raw)
    if len(masked) > 3800:
        masked = masked[:3800] + "\n…"
    await update.message.reply_html(
        f"🔑 <b>.env (masked)</b>\n<pre>{masked}</pre>"
    )


async def cmd_backup(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/backup — SCP voodoo.db from server to /tmp and send as document."""
    if not _is_admin(update):
        return
    date_str = datetime.now().strftime("%Y%m%d")
    tmp_path = f"/tmp/voodoo_backup_{date_str}.db"
    msg = await update.message.reply_html("📦 Завантажую резервну копію БД…")
    try:
        proc = await asyncio.create_subprocess_exec(
            "scp", "-o", "StrictHostKeyChecking=no",
            "-i", str(SSH_KEY),
            f"root@{SSH_IP}:/opt/voodoo/database/voodoo.db",
            tmp_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=60)
        rc = proc.returncode
    except asyncio.TimeoutError:
        await msg.edit_text("⏱ SCP timeout (60 s)")
        return
    except Exception as e:
        await msg.edit_text(f"❌ SCP error: {e}")
        return

    if rc != 0:
        err = stderr_b.decode(errors="replace").strip()
        await msg.edit_text(f"❌ SCP failed (rc={rc}):\n{err[:500]}")
        return

    await msg.edit_text("✅ Резервну копію отримано. Надсилаю файл…")
    try:
        await update.message.reply_document(
            document=open(tmp_path, "rb"),
            filename=f"voodoo_backup_{date_str}.db",
            caption=f"📦 Backup voodoo.db — {date_str}",
        )
    except Exception as e:
        await update.message.reply_html(f"❌ Не вдалося надіслати файл: {e}")
    finally:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass


async def cmd_localrun(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/localrun — start all bots locally via run.sh."""
    if not _is_admin(update):
        return
    run_sh = Path(__file__).parent.parent / "run.sh"
    if not run_sh.exists():
        await update.message.reply_html("❌ <code>run.sh</code> не знайдено.")
        return
    msg = await update.message.reply_html("🚀 Запускаю боти локально…")
    try:
        proc = await asyncio.create_subprocess_exec(
            "bash", str(run_sh), "all",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(run_sh.parent),
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=15)
            output = (stdout_b + stderr_b).decode(errors="replace").strip()
        except asyncio.TimeoutError:
            output = "Boти запущено у фоні (timeout 15 s — це нормально)."
    except Exception as e:
        await msg.edit_text(f"❌ Помилка запуску: {e}")
        return
    if len(output) > 3800:
        output = output[:3800] + "\n…"
    await msg.edit_text(
        f"🚀 <b>Local run output:</b>\n<code>{output or 'OK'}</code>",
        parse_mode="HTML",
    )


async def cmd_localstop(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/localstop — kill all local bot processes."""
    if not _is_admin(update):
        return
    patterns = [
        "voodoo_bot.py",
        "voodoo_speak_bot.py",
        "voodoo_teacher_bot.py",
        "voodoo_publisher_bot.py",
        "voodoo_analyst_bot.py",
        "voodoo_growth_bot.py",
        "voodoo_ops_bot.py",
        "voodoo_group_manager.py",
        "voodoo_content_scheduler.py",
    ]
    results = []
    for pat in patterns:
        r = subprocess.run(["pkill", "-f", pat], capture_output=True)
        icon = "✅" if r.returncode == 0 else "—"
        results.append(f"{icon} {pat}")
    await update.message.reply_html(
        "🛑 <b>Local stop results:</b>\n" + "\n".join(results)
    )


# ══════════════════════════════════════════════════════════════════════════════
# OUTREACH CONTROL COMMANDS
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_outreach(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/outreach — inline dashboard for the outreach agent."""
    if not _is_admin(update):
        return
    from agents.outreach_agent import get_stats_text
    try:
        text = get_stats_text()
    except Exception as e:
        text = f"❌ Cannot load stats: {e}"

    keyboard = [
        [
            InlineKeyboardButton("🟢 SOFT mode",       callback_data="out_mode_soft"),
            InlineKeyboardButton("🟡 AGGR mode",        callback_data="out_mode_aggressive"),
        ],
        [
            InlineKeyboardButton("▶️ Run now (all)",    callback_data="out_run_all"),
            InlineKeyboardButton("▶️ Run UA",           callback_data="out_run_ua"),
            InlineKeyboardButton("▶️ Run RU",           callback_data="out_run_ru"),
        ],
        [
            InlineKeyboardButton("⏸ Pause 6h",         callback_data="out_pause_6"),
            InlineKeyboardButton("⏸ Pause 24h",        callback_data="out_pause_24"),
            InlineKeyboardButton("▶️ Resume",           callback_data="out_resume"),
        ],
        [
            InlineKeyboardButton("🎓 Learning",         callback_data="out_learn"),
            InlineKeyboardButton("🚫 Blacklist",        callback_data="out_blacklist"),
            InlineKeyboardButton("🔄 Reset learn",      callback_data="out_resetlearn"),
        ],
        [
            InlineKeyboardButton("🌍 Markets",          callback_data="out_markets"),
            InlineKeyboardButton("⚙️ Settings",         callback_data="out_settings"),
        ],
    ]
    await update.message.reply_html(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def cmd_outmode(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/outmode soft|aggressive [market] — switch outreach mode."""
    if not _is_admin(update):
        return
    args = ctx.args or []
    if not args:
        await update.message.reply_html(
            "Використання:\n"
            "<code>/outmode soft</code>\n"
            "<code>/outmode aggressive</code>\n"
            "<code>/outmode soft ru</code> — тільки для ринку"
        )
        return
    from agents.outreach_agent import set_mode
    mode   = args[0].lower()
    market = args[1] if len(args) > 1 else None
    await update.message.reply_html(set_mode(mode, market))


async def cmd_outpause(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/outpause [hours] [market] — pause outreach."""
    if not _is_admin(update):
        return
    from agents.outreach_agent import set_pause
    args   = ctx.args or []
    hours  = float(args[0]) if args else 6.0
    market = args[1] if len(args) > 1 else None
    await update.message.reply_html(set_pause(hours, market))


async def cmd_outresume(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/outresume [market] — resume outreach."""
    if not _is_admin(update):
        return
    from agents.outreach_agent import set_resume
    market = ctx.args[0] if ctx.args else None
    await update.message.reply_html(set_resume(market))


async def cmd_outrun(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/outrun [market] — trigger outreach cycle now."""
    if not _is_admin(update):
        return
    market = ctx.args[0] if ctx.args else None
    msg = await update.message.reply_html(
        f"📣 Запускаю outreach{' для '+market if market else ''}…"
    )
    from agents.outreach_agent import run_outreach_cycle
    try:
        await run_outreach_cycle(market)
        await msg.edit_text("✅ Outreach цикл завершено. Дивись звіт вище.")
    except Exception as e:
        await msg.edit_text(f"❌ Помилка: {e}")


async def cmd_outstats(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/outstats — full outreach stats."""
    if not _is_admin(update):
        return
    from agents.outreach_agent import get_stats_text
    try:
        await update.message.reply_html(get_stats_text())
    except Exception as e:
        await update.message.reply_html(f"❌ {e}")


async def cmd_outlearn(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/outlearn — show what the agent has learned (ban patterns, best times, etc.)."""
    if not _is_admin(update):
        return
    from agents.outreach_agent import LearningEngine
    engine = LearningEngine()
    await update.message.reply_html(engine.summary_text())


async def cmd_outcooldown(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/outcooldown [hours] — set cooldown between posts to same group."""
    if not _is_admin(update):
        return
    if not ctx.args or not ctx.args[0].isdigit():
        await update.message.reply_html("Використання: <code>/outcooldown 48</code>")
        return
    from agents.outreach_agent import set_cooldown
    await update.message.reply_html(set_cooldown(float(ctx.args[0])))


async def cmd_outdelay(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/outdelay [min] [max] — set delay in seconds between posts."""
    if not _is_admin(update):
        return
    args = ctx.args or []
    if len(args) < 2:
        await update.message.reply_html("Використання: <code>/outdelay 20 60</code>")
        return
    from agents.outreach_agent import set_delay
    await update.message.reply_html(set_delay(float(args[0]), float(args[1])))


async def cmd_outblacklist(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/outblacklist [reset|reset all|reset group_id] — manage blacklist."""
    if not _is_admin(update):
        return
    from agents.outreach_agent import LearningEngine, reset_blacklist
    args = ctx.args or []

    if args and args[0] == "reset":
        gid = args[1] if len(args) > 1 else None
        await update.message.reply_html(reset_blacklist(gid))
        return

    engine = LearningEngine()
    banned = engine.data["banned_groups"]
    if not banned:
        await update.message.reply_html("🚫 Blacklist порожній")
        return
    lines = ["🚫 <b>Чорний список груп:</b>\n"]
    for gid in banned[:30]:
        lines.append(f"• <code>{gid}</code>")
    if len(banned) > 30:
        lines.append(f"… та ще {len(banned)-30}")
    lines.append("\n<code>/outblacklist reset [group_id]</code> — видалити")
    lines.append("<code>/outblacklist reset all</code> — очистити все")
    await update.message.reply_html("\n".join(lines))


async def cmd_markets(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/markets — show market status + scaling controls."""
    if not _is_admin(update):
        return
    from agents.scaling_manager import load_configs
    cfg = load_configs()

    lines = ["🌍 <b>Voodoo Markets</b>\n"]
    keyboard = []
    for code, m in cfg["markets"].items():
        status = m["status"]
        gid    = m.get("group_id", 0)
        icon   = {"active": "✅", "pending": "⏳", "planned": "📋"}.get(status, "❓")
        lines.append(f"{icon} {m['flag']} <b>{m['language']}</b> [{code}]")
        lines.append(f"   Status: {status} | Group: {'<code>'+str(gid)+'</code>' if gid else '—'}")
        if status == "pending":
            keyboard.append([InlineKeyboardButton(
                f"🚀 Bootstrap {m['flag']} {code.upper()}",
                callback_data=f"scale_{code}",
            )])

    lines.append("\n💡 <code>/scale ru</code> — bootstrap новий ринок")

    await update.message.reply_html(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None,
    )


async def cmd_scale(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/scale [market] — bootstrap a new language market."""
    if not _is_admin(update):
        return
    if not ctx.args:
        await update.message.reply_html("Використання: <code>/scale ru</code>")
        return
    market = ctx.args[0].lower()
    msg = await update.message.reply_html(f"🚀 Bootstrapping <b>{market}</b> market…")
    from agents.scaling_manager import bootstrap_market
    try:
        await bootstrap_market(market)
        await msg.edit_text(f"✅ Market <b>{market}</b> bootstrapped! Перевір OpsBot для деталей.")
    except Exception as e:
        await msg.edit_text(f"❌ Bootstrap failed: {e}")


# ── Callbacks for outreach inline buttons ─────────────────────────────────────

async def cb_outreach(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data  = query.data

    from agents.outreach_agent import (
        set_mode, set_pause, set_resume,
        LearningEngine, get_stats_text, run_outreach_cycle, save_learning, load_learning,
    )
    from agents.scaling_manager import load_configs

    if data == "out_mode_soft":
        await query.edit_message_text(set_mode("soft"), parse_mode="HTML")

    elif data == "out_mode_aggressive":
        await query.edit_message_text(set_mode("aggressive"), parse_mode="HTML")

    elif data.startswith("out_run_"):
        market = data.split("out_run_")[1]
        market = None if market == "all" else market
        await query.edit_message_text(f"📣 Запускаю outreach{' для '+market if market else ''}…", parse_mode="HTML")
        asyncio.get_event_loop().create_task(run_outreach_cycle(market))

    elif data.startswith("out_pause_"):
        hours = float(data.split("out_pause_")[1])
        await query.edit_message_text(set_pause(hours), parse_mode="HTML")

    elif data == "out_resume":
        await query.edit_message_text(set_resume(), parse_mode="HTML")

    elif data == "out_learn":
        engine = LearningEngine()
        await query.edit_message_text(engine.summary_text(), parse_mode="HTML")

    elif data == "out_blacklist":
        engine = LearningEngine()
        banned = engine.data["banned_groups"]
        text = f"🚫 В чорному списку: {len(banned)} груп"
        if banned:
            text += "\n" + "\n".join(f"• <code>{g}</code>" for g in banned[:20])
        await query.edit_message_text(text, parse_mode="HTML")

    elif data == "out_resetlearn":
        l = load_learning()
        l["hourly_stats"] = {}
        l["template_stats"] = {}
        l["current_delays"] = {"min": 15, "max": 45}
        l["adaptations"] = []
        save_learning(l)
        await query.edit_message_text("✅ Learning статистика скинута (blacklist збережено)", parse_mode="HTML")

    elif data == "out_markets":
        cfg = load_configs()
        lines = ["🌍 <b>Markets:</b>"]
        for code, m in cfg["markets"].items():
            status = m["status"]
            icon   = {"active": "✅", "pending": "⏳", "planned": "📋"}.get(status, "❓")
            lines.append(f"{icon} {m['flag']} {code}: {status}")
        await query.edit_message_text("\n".join(lines), parse_mode="HTML")

    elif data == "out_settings":
        from agents.outreach_agent import load_runtime
        rt   = load_runtime()
        text = (
            f"⚙️ <b>Outreach Settings</b>\n\n"
            f"Mode: <b>{rt.get('mode')}</b>\n"
            f"Cooldown: <b>{rt.get('cooldown_hours')}h</b>\n"
            f"Delay: <b>{rt.get('delay_min')}–{rt.get('delay_max')}s</b>\n"
            f"Max posts/cycle: <b>{rt.get('max_groups_per_run')}</b>\n\n"
            f"Змінити:\n"
            f"<code>/outmode soft|aggressive</code>\n"
            f"<code>/outcooldown 24</code>\n"
            f"<code>/outdelay 20 60</code>"
        )
        await query.edit_message_text(text, parse_mode="HTML")

    elif data.startswith("scale_"):
        market = data.split("scale_")[1]
        await query.edit_message_text(f"🚀 Bootstrapping {market}…", parse_mode="HTML")
        from agents.scaling_manager import bootstrap_market
        asyncio.get_event_loop().create_task(bootstrap_market(market))


async def cmd_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/menu — inline keyboard with all available commands grouped by category."""
    if not _is_admin(update):
        return
    keyboard = [
        [
            InlineKeyboardButton("📊 Dashboard",   switch_inline_query_current_chat="/dashboard"),
            InlineKeyboardButton("📈 Stats",        switch_inline_query_current_chat="/stats"),
        ],
        [
            InlineKeyboardButton("🖥 Status (local)",  switch_inline_query_current_chat="/status"),
            InlineKeyboardButton("🖥 Status (server)", switch_inline_query_current_chat="/srvstatus"),
        ],
        [
            InlineKeyboardButton("📋 Logs (local)",    switch_inline_query_current_chat="/logs ops_bot"),
            InlineKeyboardButton("📋 Logs (server)",   switch_inline_query_current_chat="/serverlogs voodoo_bot 30"),
        ],
        [
            InlineKeyboardButton("📣 Outreach Panel", switch_inline_query_current_chat="/outreach"),
            InlineKeyboardButton("🌍 Markets",         switch_inline_query_current_chat="/markets"),
        ],
        [
            InlineKeyboardButton("🎓 Outreach Learn", switch_inline_query_current_chat="/outlearn"),
            InlineKeyboardButton("📊 Outreach Stats", switch_inline_query_current_chat="/outstats"),
        ],
        [
            InlineKeyboardButton("🚀 Deploy all",   switch_inline_query_current_chat="/deploy"),
            InlineKeyboardButton("💻 SSH shell",    switch_inline_query_current_chat="/sh uptime"),
        ],
        [
            InlineKeyboardButton("📦 Backup DB",    switch_inline_query_current_chat="/backup"),
            InlineKeyboardButton("📢 Post public",  switch_inline_query_current_chat="/public "),
        ],
        [
            InlineKeyboardButton("🔑 Show .env",    switch_inline_query_current_chat="/env"),
            InlineKeyboardButton("⏳ Approvals",     switch_inline_query_current_chat="/approvals"),
        ],
        [
            InlineKeyboardButton("🤖 AI Analyze",   switch_inline_query_current_chat="/analyze"),
            InlineKeyboardButton("📅 Plan week",     switch_inline_query_current_chat="/plan"),
        ],
        [
            InlineKeyboardButton("☁️ Cloud",        switch_inline_query_current_chat="/cloud"),
            InlineKeyboardButton("🔄 Failover",      switch_inline_query_current_chat="/failover"),
        ],
        [
            InlineKeyboardButton("▶️ Local run",    switch_inline_query_current_chat="/localrun"),
            InlineKeyboardButton("⏹ Local stop",    switch_inline_query_current_chat="/localstop"),
        ],
    ]
    await update.message.reply_html(
        "🎛 <b>VoodooOpsBot — Menu</b>\n\n"
        "Вибери команду або набери її вручну:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


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
    app.add_handler(CommandHandler("retention", cmd_retention, filters=admin_filter))
    app.add_handler(CommandHandler("top",       cmd_top,      filters=admin_filter))
    app.add_handler(CommandHandler("improve",   cmd_improve,  filters=admin_filter))
    app.add_handler(CommandHandler("plan",      cmd_plan,     filters=admin_filter))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast, filters=admin_filter))
    app.add_handler(CommandHandler("raffle",    cmd_raffle,   filters=admin_filter))

    app.add_handler(CommandHandler("cloud",      cmd_cloud,      filters=admin_filter))
    app.add_handler(CommandHandler("cloudstart", cmd_cloudstart, filters=admin_filter))
    app.add_handler(CommandHandler("cloudstop",  cmd_cloudstop,  filters=admin_filter))
    app.add_handler(CommandHandler("cloudnew",   cmd_cloudnew,   filters=admin_filter))
    app.add_handler(CommandHandler("failover",   cmd_failover,   filters=admin_filter))

    # ── New server/ops commands ────────────────────────────────────────────────
    app.add_handler(CommandHandler("sh",           cmd_sh,          filters=admin_filter))
    app.add_handler(CommandHandler("deploy",       cmd_deploy,      filters=admin_filter))
    app.add_handler(CommandHandler("serverlogs",   cmd_serverlogs,  filters=admin_filter))
    app.add_handler(CommandHandler("srvstatus",    cmd_srvstatus,   filters=admin_filter))
    app.add_handler(CommandHandler("srvrestart",   cmd_srvrestart,  filters=admin_filter))
    app.add_handler(CommandHandler("public",       cmd_public,      filters=admin_filter))
    app.add_handler(CommandHandler("env",          cmd_env,         filters=admin_filter))
    app.add_handler(CommandHandler("backup",       cmd_backup,      filters=admin_filter))
    app.add_handler(CommandHandler("localrun",     cmd_localrun,    filters=admin_filter))
    app.add_handler(CommandHandler("localstop",    cmd_localstop,   filters=admin_filter))
    app.add_handler(CommandHandler("menu",         cmd_menu,        filters=admin_filter))

    # ── Outreach control commands ──────────────────────────────────────────────
    app.add_handler(CommandHandler("outreach",     cmd_outreach,     filters=admin_filter))
    app.add_handler(CommandHandler("outmode",      cmd_outmode,      filters=admin_filter))
    app.add_handler(CommandHandler("outpause",     cmd_outpause,     filters=admin_filter))
    app.add_handler(CommandHandler("outresume",    cmd_outresume,    filters=admin_filter))
    app.add_handler(CommandHandler("outrun",       cmd_outrun,       filters=admin_filter))
    app.add_handler(CommandHandler("outstats",     cmd_outstats,     filters=admin_filter))
    app.add_handler(CommandHandler("outlearn",     cmd_outlearn,     filters=admin_filter))
    app.add_handler(CommandHandler("outcooldown",  cmd_outcooldown,  filters=admin_filter))
    app.add_handler(CommandHandler("outdelay",     cmd_outdelay,     filters=admin_filter))
    app.add_handler(CommandHandler("outblacklist", cmd_outblacklist, filters=admin_filter))
    app.add_handler(CommandHandler("markets",      cmd_markets,      filters=admin_filter))
    app.add_handler(CommandHandler("scale",        cmd_scale,        filters=admin_filter))

    app.add_handler(CallbackQueryHandler(cb_restart,    pattern=r"^restart_"))
    app.add_handler(CallbackQueryHandler(cb_approval,   pattern=r"^(approve|reject)_"))
    app.add_handler(CallbackQueryHandler(cb_broadcast,  pattern=r"^broadcast_"))
    app.add_handler(CallbackQueryHandler(cb_cloudstop,  pattern=r"^cloudstop_"))
    app.add_handler(CallbackQueryHandler(cb_cloudnew,   pattern=r"^cloudnew_"))
    app.add_handler(CallbackQueryHandler(cb_failover,   pattern=r"^failover_"))
    app.add_handler(CallbackQueryHandler(cb_srvrestart, pattern=r"^srvrestart_"))
    app.add_handler(CallbackQueryHandler(cb_outreach,   pattern=r"^(out_|scale_)"))

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    log.info("VoodooOpsBot online (admin_id=%d)", ADMIN_ID)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
