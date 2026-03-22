"""
bots/voodoo_teacher_bot.py — VoodooTeacherBot

Focused on explanations: words, grammar, phrases, mistakes.
Uses Claude for deep contextual explanations.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
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
from agents import run_agent

load_dotenv()

logging.basicConfig(
    format="%(asctime)s [teacher_bot] %(levelname)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("teacher_bot")

TOKEN = os.getenv("VOODOO_TEACHER_BOT_TOKEN", "")
if not TOKEN:
    raise RuntimeError("VOODOO_TEACHER_BOT_TOKEN not set")

TEACHER_SYSTEM = """Ти — Voodoo Teacher, AI-вчитель англійської для українськомовних користувачів.

ПРАВИЛА:
• Пояснюй зрозуміло, з прикладами
• Вказуй IPA вимову для нових слів: /wɜːd/
• Порівнюй з українськими аналогами де корисно
• Формат: HTML Telegram (<b>, <i>, <code>)
• Відповідь: max 300 слів, структуровано
• Мова відповіді: українська (навчальний матеріал — англійська)

Якщо питання не про англійську — делікатно перенаправ."""


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await db.get_user(user.id, user.first_name or "", user.username or "")
    await update.message.reply_html(
        "📚 <b>VoodooTeacherBot</b>\n\n"
        "Я поясню будь-яке слово, фразу або граматику!\n\n"
        "<b>Команди:</b>\n"
        "/explain [слово/фраза] — детальне пояснення\n"
        "/grammar [тема] — граматичне правило\n"
        "/idiom [ідіома] — пояснення ідіоми\n"
        "/example [слово] — 5 прикладів речень\n"
        "/compare [ua слово] — аналог в англійській\n\n"
        "Або просто <b>напиши слово/речення</b> — я поясню!"
    )


async def cmd_explain(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    text = " ".join(ctx.args) if ctx.args else ""
    if not text:
        await update.message.reply_text("Використання: /explain [слово або фраза]")
        return
    msg = await update.message.reply_text("🤔 Пояснюю...")
    try:
        result = run_agent(
            system_prompt=TEACHER_SYSTEM,
            user_message=f"Детально поясни: «{text}». Включи: значення, IPA, приклади, типові помилки.",
            tools=[],
        )
        await msg.edit_text(result[:4000], parse_mode="HTML")
    except Exception as e:
        await msg.edit_text(f"❌ Помилка: {e}")


async def cmd_grammar(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    topic = " ".join(ctx.args) if ctx.args else ""
    if not topic:
        await update.message.reply_text("Використання: /grammar [тема, напр. Present Perfect]")
        return
    msg = await update.message.reply_text("📖 Готую пояснення...")
    try:
        result = run_agent(
            system_prompt=TEACHER_SYSTEM,
            user_message=f"Поясни граматичне правило: {topic}. Структура: формула, коли використовувати, 3 приклади, типові помилки.",
            tools=[],
        )
        await msg.edit_text(result[:4000], parse_mode="HTML")
    except Exception as e:
        await msg.edit_text(f"❌ Помилка: {e}")


async def cmd_idiom(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    idiom = " ".join(ctx.args) if ctx.args else ""
    if not idiom:
        await update.message.reply_text("Використання: /idiom [ідіома, напр. break a leg]")
        return
    msg = await update.message.reply_text("💬 Аналізую ідіому...")
    try:
        result = run_agent(
            system_prompt=TEACHER_SYSTEM,
            user_message=f"Поясни ідіому: «{idiom}». Включи: буквальний + фігуральний сенс, походження, 2-3 приклади, варіанти вживання.",
            tools=[],
        )
        await msg.edit_text(result[:4000], parse_mode="HTML")
    except Exception as e:
        await msg.edit_text(f"❌ Помилка: {e}")


async def cmd_example(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    word = " ".join(ctx.args) if ctx.args else ""
    if not word:
        await update.message.reply_text("Використання: /example [слово]")
        return
    msg = await update.message.reply_text("✍️ Складаю речення...")
    try:
        result = run_agent(
            system_prompt=TEACHER_SYSTEM,
            user_message=f"Дай 5 різних прикладів речень з «{word}» — від простих до складних. Переклади кожне.",
            tools=[],
        )
        await msg.edit_text(result[:4000], parse_mode="HTML")
    except Exception as e:
        await msg.edit_text(f"❌ Помилка: {e}")


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    if update.effective_chat.type != "private":
        return
    text = update.message.text.strip()
    if len(text) > 500:
        await update.message.reply_text("Будь ласка, скорочуй запит до 500 символів.")
        return
    msg = await update.message.reply_text("🤔 Думаю...")
    try:
        result = run_agent(
            system_prompt=TEACHER_SYSTEM,
            user_message=text,
            tools=[],
        )
        await msg.edit_text(result[:4000], parse_mode="HTML")
    except Exception as e:
        await msg.edit_text(f"❌ Помилка: {e}")


async def main() -> None:
    db.init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("explain", cmd_explain))
    app.add_handler(CommandHandler("grammar", cmd_grammar))
    app.add_handler(CommandHandler("idiom",   cmd_idiom))
    app.add_handler(CommandHandler("example", cmd_example))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    log.info("VoodooTeacherBot online")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
