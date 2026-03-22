"""
bots/voodoo_growth_bot.py — VoodooGrowthBot

Ethical growth: referrals, invite mechanics, campaign tracking.
NO spam. NO deceptive content. NO mass blasting.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from telegram import ChatMemberUpdated, Update
from telegram.ext import (
    Application,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    filters,
)

from database import db

load_dotenv()

logging.basicConfig(
    format="%(asctime)s [growth_bot] %(levelname)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("growth_bot")

TOKEN      = os.getenv("VOODOO_GROWTH_BOT_TOKEN", "")
ADMIN_ID   = int(os.getenv("ADMIN_CHAT_ID", "0"))
CHANNEL_ID = int(os.getenv("VOODOO_CHANNEL_ID", "0"))
BOT_LINK   = "https://t.me/v00dooBot"
KYIV_TZ    = ZoneInfo("Europe/Kyiv")

if not TOKEN:
    raise RuntimeError("VOODOO_GROWTH_BOT_TOKEN not set")


# ── New member welcome ────────────────────────────────────────────────────────

async def welcome_new_member(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome to new group members."""
    if not update.chat_member:
        return
    new_member = update.chat_member.new_chat_member
    old_member = update.chat_member.old_chat_member

    # Only trigger on join (was not member, now is member)
    from telegram import ChatMember
    if old_member.status in (ChatMember.MEMBER, ChatMember.OWNER, ChatMember.ADMINISTRATOR):
        return
    if new_member.status not in (ChatMember.MEMBER,):
        return

    user = new_member.user
    if user.is_bot:
        return

    await ctx.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            f"👋 Вітаємо, <b>{user.first_name}</b>!\n\n"
            f"🪄 Ти в <b>Voodoo</b> — спільноті тих, хто вчить англійську.\n\n"
            f"Розпочни зараз → {BOT_LINK}\n"
            f"Перший урок безкоштовний!"
        ),
        parse_mode="HTML",
    )
    log.info("Welcomed new member: %s", user.id)


# ── Weekly viral post ─────────────────────────────────────────────────────────

async def job_weekly_leaderboard(ctx) -> None:
    """Monday 10:00 — post top-5 leaderboard to channel."""
    if not CHANNEL_ID:
        return
    try:
        stats = await db.get_stats()
        top5  = stats.get("top10", [])[:5]
        if not top5:
            return
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        lines  = ["🏆 <b>Топ тижня — Voodoo</b>\n"]
        for i, u in enumerate(top5):
            lines.append(f"{medals[i]} {u.get('first_name','?')} — {u.get('xp',0)} XP")
        lines.append(f"\n🎯 Увійди в ТОП → {BOT_LINK}")
        await ctx.bot.send_message(
            chat_id=CHANNEL_ID,
            text="\n".join(lines),
            parse_mode="HTML",
        )
        log.info("Weekly leaderboard posted")
    except Exception as e:
        log.error("Weekly leaderboard failed: %s", e)


def schedule_weekly_jobs(job_queue) -> None:
    now    = datetime.now(KYIV_TZ)
    monday = now + timedelta(days=(7 - now.weekday()) % 7 or 7)
    target = monday.replace(hour=10, minute=0, second=0, microsecond=0)
    delay  = max((target - now).total_seconds(), 1)
    job_queue.run_repeating(job_weekly_leaderboard, interval=7 * 86400, first=delay)
    log.info("Weekly leaderboard job scheduled in %.0f s", delay)


# ── Admin commands ────────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_html(
        "📈 <b>VoodooGrowthBot</b>\n\n"
        "Етичне зростання:\n"
        "• Welcome нових учасників\n"
        "• Тижневий лідерборд по понеділках\n"
        "• Реферальна система\n\n"
        "/growth_stats — статистика росту\n"
        "/post_leaderboard — опублікувати рейтинг зараз\n"
    )


async def cmd_growth_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        return
    stats = await db.get_stats()
    conn  = db._connect()
    refs  = conn.execute("SELECT SUM(referral_count) FROM users").fetchone()[0] or 0
    conn.close()

    await update.message.reply_html(
        f"📈 <b>Growth Stats</b>\n\n"
        f"👥 Всього: {stats['total_users']}\n"
        f"🆕 Нових сьогодні: {stats['new_today']}\n"
        f"🆕 Нових за тиждень: {stats['new_week']}\n"
        f"👥 Реферали (всього): {refs}\n"
        f"📅 WAU: {stats['active_week']}\n"
    )


async def cmd_post_leaderboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        return
    await job_weekly_leaderboard(type("ctx", (), {"bot": ctx.bot})())
    await update.message.reply_text("✅ Лідерборд опублікований")


async def main() -> None:
    db.init_db()
    app = Application.builder().token(TOKEN).build()
    admin_f = filters.User(user_id=ADMIN_ID) if ADMIN_ID else filters.ALL

    app.add_handler(CommandHandler("start",             cmd_start,            filters=admin_f))
    app.add_handler(CommandHandler("growth_stats",      cmd_growth_stats,     filters=admin_f))
    app.add_handler(CommandHandler("post_leaderboard",  cmd_post_leaderboard, filters=admin_f))
    app.add_handler(ChatMemberHandler(welcome_new_member, ChatMemberHandler.CHAT_MEMBER))

    schedule_weekly_jobs(app.job_queue)

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    log.info("VoodooGrowthBot online")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
