"""
bots/voodoo_analyst_bot.py — VoodooAnalystBot

Analytics, recommendations, auto-reports.
Admin-only. Uses Claude Agent SDK for AI analysis.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from database import db
from agents import spawn_subagent_async, ANALYST_SYSTEM

load_dotenv()

logging.basicConfig(
    format="%(asctime)s [analyst_bot] %(levelname)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("analyst_bot")

TOKEN    = os.getenv("VOODOO_ANALYST_BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))

if not TOKEN:
    raise RuntimeError("VOODOO_ANALYST_BOT_TOKEN not set")


def _is_admin(update: Update) -> bool:
    return update.effective_user is not None and update.effective_user.id == ADMIN_ID


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    await update.message.reply_html(
        "📊 <b>VoodooAnalystBot</b>\n\n"
        "/stats — поточна статистика\n"
        "/retention — DAU/WAU/MAU\n"
        "/top — ТОП-10 гравців\n"
        "/report — AI звіт\n"
        "/weekly — тижневий дайджест\n"
        "/growth — поради для росту\n"
        "/ideas — ідеї контенту\n"
        "/dashboard — повний дашборд\n"
    )


async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    stats = await db.get_stats()
    await update.message.reply_html(
        f"📊 <b>Voodoo Stats</b>\n"
        f"━━━━━━━━━━━━\n"
        f"👥 Юзерів: <b>{stats['total_users']}</b>\n"
        f"✅ Сьогодні: <b>{stats['active_today']}</b>\n"
        f"📅 Тиждень: <b>{stats['active_week']}</b>\n"
        f"📆 Місяць: <b>{stats['active_month']}</b>\n"
        f"🆕 Нових сьогодні: <b>{stats['new_today']}</b>\n"
        f"🆕 Нових за тиждень: <b>{stats['new_week']}</b>\n"
        f"⭐ Сер. XP: {stats['avg_xp']}\n"
        f"🔥 Сер. стрік: {stats['avg_streak']}д"
    )


async def cmd_retention(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    stats = await db.get_stats()
    total = stats["total_users"] or 1
    dau   = round(stats["active_today"] / total * 100, 1)
    wau   = round(stats["active_week"]  / total * 100, 1)
    mau   = round(stats["active_month"] / total * 100, 1)
    stick = round(stats["active_today"] / max(stats["active_month"], 1) * 100, 1)

    await update.message.reply_html(
        f"📊 <b>Retention</b>\n"
        f"━━━━━━━━━━━━\n"
        f"DAU: <b>{stats['active_today']}</b> ({dau}%)\n"
        f"WAU: <b>{stats['active_week']}</b> ({wau}%)\n"
        f"MAU: <b>{stats['active_month']}</b> ({mau}%)\n"
        f"Stickiness: <b>{stick}%</b>\n\n"
        f"🆕 Нових за тиждень: {stats['new_week']}"
    )


async def cmd_top(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    stats  = await db.get_stats()
    medals = ["🥇","🥈","🥉"] + ["4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    lines  = ["🏆 <b>ТОП-10</b>\n"]
    for i, u in enumerate(stats["top10"][:10]):
        lines.append(f"{medals[i]} {u.get('first_name','?')} — {u.get('xp',0)} XP 🔥{u.get('streak',0)}д")
    await update.message.reply_html("\n".join(lines))


async def _ai_analysis(update: Update, task: str) -> None:
    msg    = await update.message.reply_text("🤖 Аналізую...")
    stats  = await db.get_stats()
    result = await spawn_subagent_async(
        "analyst", ANALYST_SYSTEM,
        f"{task}\n\nДані:\n{json.dumps(stats, ensure_ascii=False)}"
    )
    await msg.edit_text(result.output[:4000], parse_mode="HTML")


async def cmd_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update): return
    await _ai_analysis(update,
        "Зроби повний аналітичний звіт: стан, тренди, топ-3 проблеми, топ-3 можливості, що зробити цього тижня.")


async def cmd_weekly(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update): return
    await _ai_analysis(update,
        "ТИЖНЕВИЙ ДАЙДЖЕСТ: що вдалось, що ні, 3 дії на наступний тиждень, прогноз активності.")


async def cmd_growth(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update): return
    await _ai_analysis(update,
        "Дай 3 конкретні поради для росту: чому йдуть юзери, що привертає нових, який контент дає реакції.")


async def cmd_ideas(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update): return
    await _ai_analysis(update,
        "Запропонуй контент-план на завтра: ранковий пост (9:00), денний (13:00), вечірнє повторення (19:00), одна фіча що підвищить залученість.")


async def cmd_dashboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    stats = await db.get_stats()
    total = stats["total_users"] or 1

    conn = db._connect()
    try:
        stars_total = conn.execute("SELECT SUM(stars_spent) FROM users").fetchone()[0] or 0
        premium     = conn.execute("SELECT COUNT(*) FROM users WHERE is_premium=1").fetchone()[0]
        did_lesson  = conn.execute("SELECT COUNT(*) FROM users WHERE total_lessons>0").fetchone()[0]
    except Exception:
        stars_total = premium = did_lesson = 0
    conn.close()

    conv   = round(did_lesson / total * 100, 1)
    stick  = round(stats["active_today"] / max(stats["active_month"], 1) * 100, 1)

    await update.message.reply_html(
        f"🎛 <b>Dashboard — {date.today()}</b>\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"👥 <b>Юзери</b>\n"
        f"  Всього: {total} | +{stats['new_week']} за тиждень\n"
        f"  DAU {stats['active_today']} / WAU {stats['active_week']} / MAU {stats['active_month']}\n"
        f"  Stickiness: <b>{stick}%</b>\n\n"
        f"📊 <b>Воронка</b>\n"
        f"  Зареєстровані: {total}\n"
        f"  → Пройшли урок: {did_lesson} ({conv}%)\n\n"
        f"⭐ <b>Монетизація</b>\n"
        f"  Stars: {stars_total} ⭐\n"
        f"  Premium: {premium}\n\n"
        f"📈 XP: {stats['avg_xp']} avg | 🔥 Стрік: {stats['avg_streak']}д avg"
    )


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update): return
    if not update.message or not update.message.text: return
    if update.effective_chat.type != "private": return
    await _ai_analysis(update, f"Питання адміна: {update.message.text}")


# ── Auto-reports ──────────────────────────────────────────────────────────────

async def _auto_report_loop(app: Application) -> None:
    sent_hours: set[int] = set()
    weekly_sent = False
    while True:
        now     = datetime.now()
        hour    = now.hour
        weekday = now.weekday()

        if weekday == 0 and hour == 9 and not weekly_sent:
            try:
                stats  = await db.get_stats()
                result = await spawn_subagent_async(
                    "analyst", ANALYST_SYSTEM,
                    f"ТИЖНЕВИЙ ДАЙДЖЕСТ (max 150 слів). Дані: {json.dumps(stats)}"
                )
                await app.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"📋 <b>Тижневий дайджест</b>\n\n{result.output}",
                    parse_mode="HTML",
                )
                weekly_sent = True
            except Exception as e:
                log.error("Weekly digest error: %s", e)

        if hour in (8, 20) and hour not in sent_hours:
            try:
                stats  = await db.get_stats()
                result = await spawn_subagent_async(
                    "analyst", ANALYST_SYSTEM,
                    f"Короткий авто-звіт {now.strftime('%H:%M')}: 3 bullet-points. Дані: {json.dumps(stats)}"
                )
                await app.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"🤖 <b>Авто-аналіз {now.strftime('%H:%M')}</b>\n\n{result.output}",
                    parse_mode="HTML",
                )
                sent_hours.add(hour)
            except Exception as e:
                log.error("Auto-report error: %s", e)

        if hour == 0:
            sent_hours.clear()
            if weekday == 1:
                weekly_sent = False

        await asyncio.sleep(55)


async def main() -> None:
    db.init_db()
    app = Application.builder().token(TOKEN).build()
    admin_f = filters.User(user_id=ADMIN_ID)

    app.add_handler(CommandHandler("start",     cmd_start,     filters=admin_f))
    app.add_handler(CommandHandler("stats",     cmd_stats,     filters=admin_f))
    app.add_handler(CommandHandler("retention", cmd_retention, filters=admin_f))
    app.add_handler(CommandHandler("top",       cmd_top,       filters=admin_f))
    app.add_handler(CommandHandler("report",    cmd_report,    filters=admin_f))
    app.add_handler(CommandHandler("weekly",    cmd_weekly,    filters=admin_f))
    app.add_handler(CommandHandler("growth",    cmd_growth,    filters=admin_f))
    app.add_handler(CommandHandler("ideas",     cmd_ideas,     filters=admin_f))
    app.add_handler(CommandHandler("dashboard", cmd_dashboard, filters=admin_f))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    log.info("VoodooAnalystBot online")
    asyncio.create_task(_auto_report_loop(app))
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
