"""
bots/voodoo_publisher_bot.py — VoodooPublisherBot

Scheduled posting to Telegram channel/group.
No teaching logic — publishing only.
Uses Claude to generate content, then posts on schedule.
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
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    JobQueue,
    filters,
)

from database import db
from agents import ask_agent, CONTENT_SYSTEM

load_dotenv()

logging.basicConfig(
    format="%(asctime)s [publisher] %(levelname)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("publisher")

TOKEN      = os.getenv("VOODOO_PUBLISHER_BOT_TOKEN", "")
ADMIN_ID   = int(os.getenv("ADMIN_CHAT_ID", "0"))
CHANNEL_ID = int(os.getenv("VOODOO_CHANNEL_ID", "0"))
KYIV_TZ    = ZoneInfo("Europe/Kyiv")

if not TOKEN:
    raise RuntimeError("VOODOO_PUBLISHER_BOT_TOKEN not set")


# ── Content generator ─────────────────────────────────────────────────────────

async def generate_word_post() -> str:
    # Get a random word from DB
    conn = db._connect()
    word = conn.execute(
        "SELECT * FROM words ORDER BY RANDOM() LIMIT 1"
    ).fetchone()
    conn.close()

    if word:
        w = dict(word)
        context = f"Слово: {w['word']} | Переклад: {w['translation']} | Рівень: {w.get('level','A2')}"
    else:
        context = "Рандомне англійське слово рівня B1"

    return await ask_agent(
        CONTENT_SYSTEM,
        f"Створи пост «Слово дня» для Telegram-каналу вивчення англійської.\n"
        f"Контекст: {context}\n\n"
        "Формат:\n"
        "🔤 WORD /aɪpɪeɪ/\n"
        "🇺🇦 Переклад\n"
        "📖 Визначення (англ.)\n"
        "💬 Приклад речення\n"
        "🇺🇦 Переклад прикладу\n"
        "🏷 #рівень #тема\n\n"
        "Telegram HTML. Живо і цікаво!",
    )


async def generate_quiz_post() -> str:
    conn = db._connect()
    words = conn.execute("SELECT * FROM words ORDER BY RANDOM() LIMIT 4").fetchall()
    conn.close()

    if len(words) >= 4:
        ws = [dict(w) for w in words]
        context = f"Слова: {[w['word'] for w in ws]}, правильна відповідь: {ws[0]['translation']}"
    else:
        context = "Будь-яке англійське слово"

    return await ask_agent(
        CONTENT_SYSTEM,
        f"Створи квіз-пост для Telegram. Контекст: {context}\n\n"
        "Формат:\n"
        "❓ Що означає: WORD?\n"
        "A) варіант\nB) варіант\nC) варіант\nD) варіант\n\n"
        "👇 Відповідь в коментарях!\n"
        "Правильна: ||D) переклад|| (spoiler)\n\n"
        "Telegram HTML.",
    )


async def generate_recap_post() -> str:
    stats = await db.get_stats()
    return await ask_agent(
        CONTENT_SYSTEM,
        f"Створи мотиваційний підсумковий пост для каналу.\n"
        f"Статистика: {stats.get('active_today',0)} учнів активних сьогодні, "
        f"топ XP: {stats['top10'][0].get('xp',0) if stats.get('top10') else 0}\n\n"
        "Короткий пост: досягнення тижня, мотивація, заклик вчитись. HTML.",
    )


# ── Scheduled jobs ────────────────────────────────────────────────────────────

async def job_morning_word(ctx) -> None:
    """09:00 — Word of the day"""
    if not CHANNEL_ID:
        log.warning("VOODOO_CHANNEL_ID not set")
        return
    try:
        text = await generate_word_post()
        await ctx.bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode="HTML")
        log.info("Morning word posted")
    except Exception as e:
        log.error("Morning word failed: %s", e)


async def job_midday_quiz(ctx) -> None:
    """13:00 — Quiz"""
    if not CHANNEL_ID:
        return
    try:
        text = await generate_quiz_post()
        await ctx.bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode="HTML")
        log.info("Midday quiz posted")
    except Exception as e:
        log.error("Midday quiz failed: %s", e)


async def job_evening_recap(ctx) -> None:
    """19:00 — Evening recap"""
    if not CHANNEL_ID:
        return
    try:
        text = await generate_recap_post()
        await ctx.bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode="HTML")
        log.info("Evening recap posted")
    except Exception as e:
        log.error("Evening recap failed: %s", e)


def schedule_daily_jobs(job_queue: JobQueue) -> None:
    now = datetime.now(KYIV_TZ)

    for hour, job_fn, name in [
        (9,  job_morning_word,  "morning_word"),
        (13, job_midday_quiz,   "midday_quiz"),
        (19, job_evening_recap, "evening_recap"),
    ]:
        target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        delay = (target - now).total_seconds()
        job_queue.run_repeating(job_fn, interval=86400, first=delay, name=name)
        log.info("Scheduled %s in %.0f seconds", name, delay)


# ── Admin commands ────────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_html(
        "📢 <b>VoodooPublisherBot</b>\n\n"
        "Публікує контент за розкладом (09:00, 13:00, 19:00 Kyiv).\n\n"
        "/post_word — опублікувати слово зараз\n"
        "/post_quiz — опублікувати квіз зараз\n"
        "/post_recap — опублікувати підсумок зараз\n"
        "/schedule — показати розклад\n"
    )


async def cmd_post_word(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        return
    msg = await update.message.reply_text("📝 Генерую слово дня...")
    try:
        text = await generate_word_post()
        if CHANNEL_ID:
            await ctx.bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
        await msg.edit_text("✅ Опубліковано!\n\nПопередній:\n" + text[:500], parse_mode="HTML")
    except Exception as e:
        await msg.edit_text(f"❌ {e}")


async def cmd_post_quiz(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        return
    msg = await update.message.reply_text("📝 Генерую квіз...")
    try:
        text = await generate_quiz_post()
        if CHANNEL_ID:
            await ctx.bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
        await msg.edit_text("✅ Опубліковано!", parse_mode="HTML")
    except Exception as e:
        await msg.edit_text(f"❌ {e}")


async def cmd_schedule(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_html(
        "📅 <b>Розклад публікацій (Kyiv)</b>\n\n"
        "09:00 — 🔤 Слово дня\n"
        "13:00 — ❓ Квіз\n"
        "19:00 — 📊 Вечірній підсумок\n\n"
        f"Канал ID: <code>{CHANNEL_ID}</code>"
    )


async def main() -> None:
    db.init_db()
    app = Application.builder().token(TOKEN).build()
    admin_f = filters.User(user_id=ADMIN_ID) if ADMIN_ID else filters.ALL

    app.add_handler(CommandHandler("start",      cmd_start,     filters=admin_f))
    app.add_handler(CommandHandler("post_word",  cmd_post_word, filters=admin_f))
    app.add_handler(CommandHandler("post_quiz",  cmd_post_quiz, filters=admin_f))
    app.add_handler(CommandHandler("schedule",   cmd_schedule,  filters=admin_f))

    schedule_daily_jobs(app.job_queue)

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    log.info("VoodooPublisherBot online — channel=%d", CHANNEL_ID)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
