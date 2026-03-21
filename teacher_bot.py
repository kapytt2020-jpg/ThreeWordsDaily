"""
teacher_bot.py — GROUP_TEACHER (Лекс)

Lives in @ThreeWordsDailyChat group. Responds to grammar questions,
trigger words, mentions, and replies. Also posts daily educator content.

Environment variables (.env):
  TEACHER_BOT_TOKEN   — bot token for the group teacher bot
  OPENAI_API_KEY      — OpenAI key
  TELEGRAM_CHAT_ID    — group/channel ID where to post (required for scheduled posts)

Run:
  python3 teacher_bot.py
"""

import asyncio
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from openai import AsyncOpenAI
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
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
CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")   # group to post into
UKRAINE_TZ = ZoneInfo("Europe/Kyiv")

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
# Blogger posts (proactive, scheduled)
# ---------------------------------------------------------------------------

BLOG_PROMPTS = {
    "grammar_tip": (
        "Напиши коротку граматичну пораду для вивчення англійської — у стилі Лекса (блогера-вчителя). "
        "Формат: одне практичне правило + 2 приклади (правильно ✅ / неправильно ❌). "
        "Українська мова. Починай з емодзі та заголовку. Максимум 150 слів. "
        "Тема: випадкова граматична тема (артиклі / часи / прийменники / модальні / умовні / порядок слів / etc)."
    ),
    "did_you_know": (
        "Напиши цікавий факт про англійську мову — у стилі Лекса (ентузіаст і блогер). "
        "Щось несподіване: етимологія слова, дивне правило, культурний контекст. "
        "Українська мова. Починай з '🤯 Знав(ла)?' або '💡 Цікаво!'. Максимум 120 слів."
    ),
    "common_mistake": (
        "Напиши пост про типову помилку українців в англійській — у стилі Лекса. "
        "Формат: помилка → пояснення чому → виправлення. "
        "Приклади з реального життя. Ukrainian language. Start with '⚠️ Часта помилка:'. Максимум 140 слів."
    ),
}

async def _post_to_group(ctx, prompt_key: str) -> None:
    if not CHAT_ID:
        log.warning("TELEGRAM_CHAT_ID not set — skipping group post")
        return
    try:
        prompt = BLOG_PROMPTS[prompt_key]
        r = await ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": prompt},
            ],
            max_tokens=350,
            temperature=0.85,
        )
        text = r.choices[0].message.content.strip()
        await ctx.bot.send_message(chat_id=CHAT_ID, text=text, parse_mode="HTML")
        log.info("Posted '%s' to group %s", prompt_key, CHAT_ID)
    except Exception as exc:
        log.error("Group post error (%s): %s", prompt_key, exc)


async def job_grammar_tip(ctx) -> None:
    """11:00 Kyiv — Grammar tip of the day."""
    await _post_to_group(ctx, "grammar_tip")


async def job_did_you_know(ctx) -> None:
    """15:00 Kyiv — Did you know? fun English fact."""
    await _post_to_group(ctx, "did_you_know")


async def job_common_mistake(ctx) -> None:
    """18:00 Kyiv — Common Ukrainian mistake in English."""
    await _post_to_group(ctx, "common_mistake")


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
    app = ApplicationBuilder().token(TEACHER_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Scheduled blogger posts
    jq = app.job_queue
    if jq and CHAT_ID:
        jq.run_daily(
            job_grammar_tip,
            time=datetime.now(UKRAINE_TZ).replace(hour=11, minute=0, second=0, microsecond=0).timetz(),
            name="grammar_tip",
        )
        jq.run_daily(
            job_did_you_know,
            time=datetime.now(UKRAINE_TZ).replace(hour=15, minute=0, second=0, microsecond=0).timetz(),
            name="did_you_know",
        )
        jq.run_daily(
            job_common_mistake,
            time=datetime.now(UKRAINE_TZ).replace(hour=18, minute=0, second=0, microsecond=0).timetz(),
            name="common_mistake",
        )
        log.info("Scheduled 3 daily group posts (11:00 / 15:00 / 18:00 Kyiv)")
    elif not CHAT_ID:
        log.warning("TELEGRAM_CHAT_ID not set — scheduled group posts disabled")

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    log.info("teacher_bot (Лекс) is online")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
