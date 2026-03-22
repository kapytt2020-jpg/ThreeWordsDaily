"""
bots/voodoo_speak_bot.py — VoodooSpeakBot

Pronunciation, voice transcription, speaking practice.
Uses OpenAI Whisper for speech-to-text + GPT for feedback.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

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

from database import db

load_dotenv()

logging.basicConfig(
    format="%(asctime)s [speak_bot] %(levelname)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("speak_bot")

TOKEN    = os.getenv("VOODOO_SPEAK_BOT_TOKEN", "")
OAI_KEY  = os.getenv("OPENAI_API_KEY", "")

if not TOKEN:
    raise RuntimeError("VOODOO_SPEAK_BOT_TOKEN not set")

ai = AsyncOpenAI(api_key=OAI_KEY) if OAI_KEY else None

PRONUNCIATION_SYSTEM = """Ти — AI-тренер вимови англійської для українськомовних.

Отримуєш транскрипцію голосового повідомлення студента і слово/фразу яку він практикував.

Дай:
1. 🎯 Що сказано правильно
2. ⚠️ Що покращити (конкретно)
3. 📢 IPA транскрипцію правильної вимови
4. 💡 Підказка: як Ukrainian speakers часто помиляються з цим звуком
5. 🔄 Практичне завдання: повтори X разів з фокусом на Y

Відповідь: коротка, підбадьорлива, українська."""


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await db.get_user(user.id, user.first_name or "", user.username or "")
    await update.message.reply_html(
        "🔊 <b>VoodooSpeakBot</b>\n\n"
        "Тренуй вимову англійських слів!\n\n"
        "<b>Як це працює:</b>\n"
        "1. Надішли голосове повідомлення з англійським словом\n"
        "2. Я транскрибую і дам детальний фідбек по вимові\n\n"
        "<b>Команди:</b>\n"
        "/pronounce [слово] — IPA + опис вимови\n"
        "/practice [слово] — режим тренування\n"
        "/sounds — таблиця проблемних звуків\n\n"
        "🎤 Або просто <b>надішли голосове</b>!"
    )


async def cmd_pronounce(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    word = " ".join(ctx.args) if ctx.args else ""
    if not word:
        await update.message.reply_text("Використання: /pronounce [слово або фраза]")
        return

    if not ai:
        await update.message.reply_html(
            f"🔊 <b>{word}</b>\n\n"
            "Для отримання IPA вимови потрібен OpenAI API key.\n"
            "Поки: використай Cambridge Dictionary або Forvo для аудіо.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📖 Cambridge Dict",
                                     url=f"https://dictionary.cambridge.org/dictionary/english/{word.replace(' ', '-')}"),
            ]]),
        )
        return

    msg = await update.message.reply_text("🔍 Шукаю вимову...")
    try:
        r = await ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": (
                    f"Дай IPA транскрипцію для «{word}» (US та UK варіанти якщо різні).\n"
                    "Поясни кожен складний звук для українськомовного студента.\n"
                    "Дай мнемонічну підказку для запам'ятовування вимови.\n"
                    "Формат: Telegram HTML."
                ),
            }],
            max_tokens=400,
        )
        await msg.edit_text(r.choices[0].message.content, parse_mode="HTML")
    except Exception as e:
        await msg.edit_text(f"❌ Помилка: {e}")


async def cmd_sounds(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_html(
        "📢 <b>Проблемні звуки для українців</b>\n\n"
        "<b>Відсутні в українській:</b>\n"
        "• <b>θ</b> [θ] — <i>think, three</i> → кінчик язика між зубами\n"
        "• <b>ð</b> [ð] — <i>the, this</i> → дзвінкий варіант θ\n"
        "• <b>æ</b> [æ] — <i>cat, bad</i> → між «е» і «а»\n"
        "• <b>ŋ</b> [ŋ] — <i>sing, king</i> → носовий «н» в кінці\n"
        "• <b>ɜː</b> [ɜː] — <i>bird, word</i> → нейтральний звук\n\n"
        "<b>Часті помилки:</b>\n"
        "• W [w] → не «в», а губно-губний\n"
        "• H [h] → м'яке «г», не «х»\n"
        "• R [r] → не «р», язик не вібрує\n"
        "• V [v] → зуби на губу (не «в» як в укр.)\n\n"
        "🎤 Надішли голосове для персонального фідбеку!"
    )


async def handle_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Transcribe voice message and give pronunciation feedback."""
    if not ai:
        await update.message.reply_text(
            "🔊 Функція голосового аналізу потребує OpenAI API.\n"
            "Встанови OPENAI_API_KEY в .env файлі."
        )
        return

    voice = update.message.voice
    msg   = await update.message.reply_text("🎤 Транскрибую...")

    try:
        file = await ctx.bot.get_file(voice.file_id)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp_path = tmp.name
        await file.download_to_drive(tmp_path)

        with open(tmp_path, "rb") as f:
            transcript = await ai.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language="en",
            )

        text = transcript.text.strip()
        log.info("Transcribed: %s", text)

        feedback = await ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": PRONUNCIATION_SYSTEM},
                {"role": "user", "content": f"Студент сказав: «{text}»\n\nДай фідбек по вимові."},
            ],
            max_tokens=400,
        )

        Path(tmp_path).unlink(missing_ok=True)

        await msg.edit_text(
            f"🎤 <b>Ти сказав:</b> <i>{text}</i>\n\n"
            + feedback.choices[0].message.content,
            parse_mode="HTML",
        )
    except Exception as e:
        log.error("Voice processing error: %s", e)
        await msg.edit_text(f"❌ Помилка обробки голосу: {e}")


VOODOO_BOT_TOKEN = os.getenv("VOODOO_BOT_TOKEN", "")
NUDGE_INTERVAL   = 3600   # check every hour
INACTIVE_HOURS   = 24     # nudge after 24h without activity

PET_NUDGES = [
    "🦊 {name} сумує без тебе!\n\nТвій пет чекає на урок 📚",
    "😴 {name} вже задрімав від нудьги...\n\nЗайди хоч на 5 хвилин! 🪄",
    "🌙 {name} питає: а де ти?\n\nСерія чекає — не розривай її! 🔥",
    "👀 {name} дивиться на двері вже {hours}г...\n\nОдне слово — і він знову щасливий! ✨",
]


async def _pet_nudge_loop() -> None:
    """Background job: nudge inactive users via @v00dooBot."""
    import httpx
    from datetime import datetime, timedelta

    if not VOODOO_BOT_TOKEN:
        return

    log.info("Pet nudge loop started (every %dh check, nudge after %dh inactive)", NUDGE_INTERVAL // 3600, INACTIVE_HOURS)
    await asyncio.sleep(300)  # wait 5 min after startup

    while True:
        try:
            conn = db._connect()
            cutoff = (datetime.utcnow() - timedelta(hours=INACTIVE_HOURS)).strftime("%Y-%m-%dT%H:%M")
            rows = conn.execute(
                """SELECT tg_id, first_name, pet_name, pet_character, last_active, streak
                   FROM users
                   WHERE last_active != '' AND last_active < ?
                   AND tg_id NOT IN (
                       SELECT tg_id FROM nudge_log
                       WHERE sent_at > datetime('now', '-23 hours')
                   )
                   LIMIT 50""",
                (cutoff,),
            ).fetchall()
            conn.close()
        except Exception as e:
            log.warning("Nudge query failed: %s", e)
            rows = []

        if rows:
            import random
            async with httpx.AsyncClient(timeout=10) as client:
                for row in rows:
                    tg_id    = row[0]
                    fname    = row[1] or "друже"
                    pet_name = row[2] or row[3] or "Лексик"
                    last_act = row[4] or ""
                    try:
                        if last_act:
                            from datetime import datetime as dt
                            diff = datetime.utcnow() - dt.fromisoformat(last_act.replace("Z", ""))
                            hours = int(diff.total_seconds() // 3600)
                        else:
                            hours = INACTIVE_HOURS
                    except Exception:
                        hours = INACTIVE_HOURS

                    template = random.choice(PET_NUDGES)
                    text = template.format(name=pet_name, hours=hours)

                    try:
                        await client.post(
                            f"https://api.telegram.org/bot{VOODOO_BOT_TOKEN}/sendMessage",
                            json={"chat_id": tg_id, "text": text, "parse_mode": "HTML"},
                        )
                        # Log to avoid re-nudging
                        c = db._connect()
                        c.execute(
                            "CREATE TABLE IF NOT EXISTS nudge_log (tg_id INTEGER, sent_at TEXT)"
                        )
                        c.execute(
                            "INSERT INTO nudge_log VALUES (?, datetime('now'))", (tg_id,)
                        )
                        c.commit(); c.close()
                        log.info("Nudged user %d (%s)", tg_id, pet_name)
                        await asyncio.sleep(0.1)  # avoid flood
                    except Exception as e:
                        log.debug("Nudge failed for %d: %s", tg_id, e)

        await asyncio.sleep(NUDGE_INTERVAL)


async def main() -> None:
    db.init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("pronounce", cmd_pronounce))
    app.add_handler(CommandHandler("sounds",    cmd_sounds))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    log.info("VoodooSpeakBot online")

    await asyncio.gather(asyncio.Event().wait(), _pet_nudge_loop())


if __name__ == "__main__":
    import time
    from telegram.error import Conflict
    for attempt in range(5):
        try:
            asyncio.run(main())
            break
        except Conflict:
            wait = 15 * (attempt + 1)
            log.warning("Conflict error — another instance running? Retrying in %ds (attempt %d/5)", wait, attempt + 1)
            time.sleep(wait)
    else:
        log.error("Could not start after 5 attempts — Conflict persists")
