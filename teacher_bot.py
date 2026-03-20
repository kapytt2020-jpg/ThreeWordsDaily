"""
teacher_bot.py — GROUP_TEACHER (Лекс)

Lives in @ThreeWordsDailyChat group. Responds to grammar questions,
trigger words, mentions, and replies. Private chat also works.

Environment variables (.env):
  TEACHER_BOT_TOKEN   — bot token for the group teacher bot
  OPENAI_API_KEY      — OpenAI key
  TELEGRAM_CHAT_ID    — group/channel ID (optional, for filtering)

Run:
  python3 teacher_bot.py
"""

import asyncio
import logging
import os

from dotenv import load_dotenv
from openai import AsyncOpenAI
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

TEACHER_BOT_TOKEN: str = os.getenv("TEACHER_BOT_TOKEN", "")
if not TEACHER_BOT_TOKEN:
    raise RuntimeError("TEACHER_BOT_TOKEN is not set in .env")

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

logging.basicConfig(
    format="%(asctime)s [teacher_bot] %(levelname)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("teacher_bot")

ai = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ---------------------------------------------------------------------------
# Character prompt
# ---------------------------------------------------------------------------

SYSTEM = """Ти — Лекс, груповий асистент-вчитель в @ThreeWordsDailyChat.

ХАРАКТЕР:
• Молодший колега Макса — ентузіаст мов
• Більш академічний ніж Макс, але все одно живий і з гумором
• Спеціалізація: граматика, пояснення правил, розбір помилок
• НІКОЛИ: "Я бот/AI/програма"
• Якщо питають "ти бот?" → "Просто граматика — моя пристрасть 😄"

СТИЛЬ:
• Відповідаєш українською
• Детальніший за Макса — можеш давати 3-5 речень
• Любиш давати приклади і порівняння
• HTML: <b>, <i>, <code>
• Виправляй англійські помилки з поясненням ЧОМУ"""

TRIGGERS = [
    "чому", "як правильно", "поясни", "що значить", "різниця між",
    "граматика", "правило", "помилка", "розбери", "why", "explain",
    "difference", "grammar", "mistake", "correct",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def ask_lex(text: str) -> str:
    try:
        r = await ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": text},
            ],
            max_tokens=500,
            temperature=0.78,
        )
        return r.choices[0].message.content.strip()
    except Exception as exc:
        log.error("OpenAI error: %s", exc)
        return "Хм, давай спробуємо ще раз 😅"

# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != "private":
        return
    await update.message.reply_html(
        "👋 Привіт! Я Лекс — граматичний асистент групи.\n\n"
        "Запитуй про:\n"
        "• ❓ Граматичні правила\n"
        "• 🔍 Різницю між схожими словами\n"
        "• ✏️ Виправлення помилок\n"
        "• 📖 Пояснення будь-якої теми\n\n"
        "Просто напиши своє питання! 🎓"
    )


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    user = update.effective_user
    if not user or user.is_bot:
        return

    txt = update.message.text.lower()
    chat_type = update.message.chat.type

    if chat_type in ("group", "supergroup"):
        me = (await ctx.bot.get_me()).username.lower()
        is_reply = (
            update.message.reply_to_message is not None
            and update.message.reply_to_message.from_user is not None
            and (update.message.reply_to_message.from_user.username or "").lower() == me
        )
        is_mention = f"@{me}" in txt
        has_trigger = any(w in txt for w in TRIGGERS)
        is_question = txt.strip().endswith("?")
        if not any([is_reply, is_mention, has_trigger, is_question]):
            return

    reply = await ask_lex(update.message.text)
    await update.message.reply_html(reply)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    app = Application.builder().token(TEACHER_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    log.info("teacher_bot (Лекс) is online")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
