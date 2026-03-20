"""
marketer_bot.py — MARKETER_LEADS
Outreach bot: private-chat only, funnels users toward
@ThreeWordsDailyChat and the Mini App.
Token: MARKETER_BOT_TOKEN (separate from learning_bot.py)
"""

import asyncio
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv
from openai import AsyncOpenAI
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

# ======= CONFIG =======
MARKETER_BOT_TOKEN: str = os.getenv("MARKETER_BOT_TOKEN", "")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
SHEETS_API_URL: str = os.getenv("SHEETS_API_URL", "")

GROUP_URL: str = "https://t.me/ThreeWordsDailyChat"
MINIAPP_URL: str = os.getenv("MINIAPP_URL", "https://t.me/ThreeWordsDailyBot/app")
BOT_USERNAME: str = os.getenv("MARKETER_BOT_USERNAME", "ThreeWordsDailyBot")

# Referral DB — tracks who invited whom
REFERRAL_DB: str = str(Path(__file__).parent / "referrals.db")

logging.basicConfig(
    format="%(asctime)s [marketer_bot] %(levelname)s %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

MAX_SYSTEM_PROMPT = (
    "Ти — Макс, дружній помічник з вивчення англійської мови у ThreeWordsDaily. "
    "Відповідай українською мовою. "
    "Відповідай коротко — не більше 4 речень. "
    "Ти допомагаєш з питаннями про вивчення англійської. "
    "Завжди завершуй відповідь запрошенням приєднатися до спільноти або спробувати Mini App. "
    "Не вигадуй факти. Не роби обіцянок, яких не можеш виконати."
)

MAIN_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("Приєднатися до групи", url=GROUP_URL)],
    [InlineKeyboardButton("Почати навчання", url=MINIAPP_URL)],
])


# ======= REFERRAL DB =======

def _init_referral_db() -> None:
    conn = sqlite3.connect(REFERRAL_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            referrer_id   INTEGER NOT NULL,
            referred_id   INTEGER NOT NULL,
            referred_name TEXT,
            created_at    TEXT NOT NULL,
            PRIMARY KEY (referrer_id, referred_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id    INTEGER PRIMARY KEY,
            username   TEXT,
            first_name TEXT,
            joined_at  TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def _register_user(user_id: int, username: str, first_name: str) -> bool:
    """Register user. Returns True if they are new."""
    conn = sqlite3.connect(REFERRAL_DB)
    existing = conn.execute(
        "SELECT 1 FROM users WHERE user_id=?", (user_id,)
    ).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO users(user_id, username, first_name, joined_at) VALUES(?,?,?,?)",
            (user_id, username, first_name, datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False


def _save_referral(referrer_id: int, referred_id: int, referred_name: str) -> bool:
    """Save referral link. Returns True if it's a new referral."""
    conn = sqlite3.connect(REFERRAL_DB)
    existing = conn.execute(
        "SELECT 1 FROM referrals WHERE referrer_id=? AND referred_id=?",
        (referrer_id, referred_id),
    ).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO referrals(referrer_id, referred_id, referred_name, created_at) VALUES(?,?,?,?)",
            (referrer_id, referred_id, referred_name, datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False


def _get_referral_stats(user_id: int) -> dict:
    conn = sqlite3.connect(REFERRAL_DB)
    total = conn.execute(
        "SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (user_id,)
    ).fetchone()[0]
    referred = conn.execute(
        "SELECT referred_name, created_at FROM referrals WHERE referrer_id=? ORDER BY created_at DESC LIMIT 10",
        (user_id,),
    ).fetchall()
    conn.close()
    return {"total": total, "referred": referred}


# ======= LEAD TRACKING =======

async def _track_lead(user_id: int, username: str, first_name: str, source: str) -> None:
    """Write lead to Google Sheets leads tab. Non-blocking — errors are logged, not raised."""
    if not SHEETS_API_URL:
        logger.debug("SHEETS_API_URL not set, skipping lead tracking.")
        return
    payload = {
        "action": "append",
        "row": {
            "user_id": user_id,
            "username": username or "",
            "first_name": first_name or "",
            "source": source,
            "created_at": datetime.now().isoformat(),
        },
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{SHEETS_API_URL}/leads", json=payload)
            resp.raise_for_status()
        logger.info("Lead tracked: user_id=%d source=%s", user_id, source)
    except Exception as exc:
        logger.warning("Lead tracking failed (user_id=%d): %s", user_id, exc)


# ======= OPENAI REPLY =======

async def _ai_reply(user_text: str) -> str:
    """Generate a Max reply via gpt-4o-mini. Returns a fallback string on error."""
    try:
        resp = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": MAX_SYSTEM_PROMPT},
                {"role": "user", "content": user_text},
            ],
            max_tokens=300,
            temperature=0.7,
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        logger.error("OpenAI request failed: %s", exc)
        return (
            "Вибач, зараз не можу відповісти детально. "
            "Але ти завжди можеш знайти відповідь у нашій спільноті! "
            "Приєднуйся до @ThreeWordsDailyChat або спробуй Mini App."
        )


# ======= HANDLERS =======

async def handle_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start [ref_USERID]: welcome + referral tracking."""
    if update.effective_chat is None or update.effective_chat.type != "private":
        return
    if update.effective_user is None or update.message is None:
        return

    user = update.effective_user
    args = ctx.args or []
    referrer_id: int | None = None

    # Parse referral param: /start ref_12345678
    if args and args[0].startswith("ref_"):
        try:
            referrer_id = int(args[0][4:])
            if referrer_id == user.id:
                referrer_id = None  # can't refer yourself
        except ValueError:
            referrer_id = None

    is_new = _register_user(user.id, user.username or "", user.first_name or "")

    if is_new and referrer_id:
        is_new_referral = _save_referral(referrer_id, user.id, user.first_name or "Unknown")
        if is_new_referral:
            try:
                await ctx.bot.send_message(
                    chat_id=referrer_id,
                    text=(
                        f"🎉 <b>{user.first_name}</b> приєднався по твоєму посиланню!\n"
                        f"Ти запросив ще одну людину вчити англійську 🚀"
                    ),
                    parse_mode="HTML",
                )
            except Exception:
                pass
        source = f"referral_{referrer_id}"
    else:
        source = "start"

    logger.info("/start from user_id=%d referrer=%s", user.id, referrer_id)

    welcome = (
        f"Привіт, {user.first_name}! 👋\n\n"
        "ThreeWordsDaily — це Telegram-спільнота для тих, хто вчить англійську щодня. "
        "Три нові слова, idiom і коротка практика — кожен день безкоштовно.\n\n"
        "Обирай зручний формат:"
    )

    await update.message.reply_text(welcome, reply_markup=MAIN_KEYBOARD)

    asyncio.create_task(
        _track_lead(
            user_id=user.id,
            username=user.username or "",
            first_name=user.first_name or "",
            source=source,
        )
    )


async def handle_invite(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the user their personal referral link."""
    if update.effective_chat is None or update.effective_chat.type != "private":
        return
    if update.effective_user is None or update.message is None:
        return

    user = update.effective_user
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user.id}"
    stats = _get_referral_stats(user.id)

    lines = [
        f"🔗 <b>Твоє реферальне посилання:</b>",
        f"<code>{ref_link}</code>",
        f"",
        f"Поділись з друзями — і вони почнуть вчити англійську разом з тобою!",
        f"",
        f"👥 <b>Твої запрошені:</b> {stats['total']}",
    ]
    if stats["referred"]:
        lines.append("")
        for name, dt in stats["referred"]:
            date_str = dt[:10] if dt else "?"
            lines.append(f"  • {name} ({date_str})")

    await update.message.reply_html(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Поділитися посиланням", switch_inline_query=f"Вчи англійську безкоштовно! 👉 {ref_link}")],
        ]),
    )


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle any text message with an AI reply. Private chat only."""
    if update.effective_chat is None or update.effective_chat.type != "private":
        return
    if update.message is None or not update.message.text:
        return
    if update.effective_user is None or update.effective_user.is_bot:
        return

    user_text = update.message.text.strip()
    user = update.effective_user
    logger.info("Message from user_id=%d: %s", user.id, user_text[:80])

    reply = await _ai_reply(user_text)
    await update.message.reply_text(reply, reply_markup=MAIN_KEYBOARD)


# ======= MAIN =======

async def main() -> None:
    if not MARKETER_BOT_TOKEN:
        raise RuntimeError(
            "MARKETER_BOT_TOKEN is not set. Add it to your .env file."
        )

    _init_referral_db()

    app = Application.builder().token(MARKETER_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",  handle_start))
    app.add_handler(CommandHandler("invite", handle_invite))
    app.add_handler(CommandHandler("ref",    handle_invite))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    logger.info("marketer_bot online.")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
