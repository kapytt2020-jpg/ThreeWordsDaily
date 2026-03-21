"""
speak_bot.py — SpeakBetterrbot (@SpeakBetterrbot)

Role in @ThreeWordsDailyChat:
  • Pronunciation tips + IPA breakdown on demand
  • Daily 21:00 speaking challenge (based on curriculum theme)
  • Voice message analysis: transcribes and gives feedback (if voice sent)
  • Private chat: personalized pronunciation coach

Token: SPEAK_BOT_TOKEN
Group: posts to TELEGRAM_CHAT_ID at 21:00 daily
"""

from __future__ import annotations

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
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SPEAK_BOT_TOKEN: str = os.getenv("SPEAK_BOT_TOKEN", "")
if not SPEAK_BOT_TOKEN:
    raise RuntimeError("SPEAK_BOT_TOKEN is not set in .env")

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
CHAT_ID: int = int(os.getenv("TELEGRAM_CHAT_ID", "0"))

KYIV = ZoneInfo("Europe/Kyiv")

logging.basicConfig(
    format="%(asctime)s [speak_bot] %(levelname)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("speak_bot")

ai = AsyncOpenAI(api_key=OPENAI_API_KEY)

try:
    from content_plan_9months import get_current_week_plan
    _CURRICULUM = True
except ImportError:
    _CURRICULUM = False

# ---------------------------------------------------------------------------
# AI helpers
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are SpeakBetter, a friendly English pronunciation coach for Ukrainian learners.

YOUR ROLE:
• Explain pronunciation clearly with IPA transcription
• Give tips on sounds Ukrainians struggle with (th, w, v, r, vowel length)
• Suggest minimal pairs to practice
• Keep responses short and practical — max 5 sentences
• Always give 1 example sentence to practice out loud
• Respond in Ukrainian when possible, use English for examples

STYLE:
• Warm and encouraging
• Never overwhelm with too many rules
• Use HTML: <b>, <i>, <code>
"""


async def _ai(prompt: str, max_tokens: int = 400) -> str:
    try:
        r = await ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.7,
        )
        return r.choices[0].message.content.strip()
    except Exception as exc:
        log.error("OpenAI error: %s", exc)
        return "Вибач, зараз не можу відповісти. Спробуй ще раз! 🎤"


async def _pronounce(word: str) -> str:
    return await _ai(
        f"Give a pronunciation guide for the English word: '{word}'\n\n"
        "Include:\n"
        "1. IPA transcription\n"
        "2. How to say it (syllables, stress)\n"
        "3. Common Ukrainian mistake with this word\n"
        "4. One practice sentence\n\n"
        "Format with HTML for Telegram.",
        max_tokens=350,
    )


async def _speaking_challenge() -> str:
    """Generate a daily speaking challenge based on curriculum theme."""
    if _CURRICULUM:
        plan = get_current_week_plan()
        theme = plan["theme"] if plan else "everyday English"
        words = [w["en"] for w in plan["words"][:3]] if plan else []
        theme_ctx = f"Theme: {theme}. Practice these words: {', '.join(words)}."
    else:
        theme_ctx = "Theme: everyday English."

    return await _ai(
        f"Create a 30-second speaking challenge for Ukrainian English learners.\n"
        f"{theme_ctx}\n\n"
        "Format for Telegram (HTML):\n"
        "<b>🎤 Speaking Challenge — [time]</b>\n\n"
        "<b>Topic:</b> [1 sentence topic]\n\n"
        "<b>Your task:</b> Say 3-5 sentences about this topic out loud!\n\n"
        "<b>Key words to use:</b>\n"
        "• <b>word1</b> /IPA/\n"
        "• <b>word2</b> /IPA/\n"
        "• <b>word3</b> /IPA/\n\n"
        "<i>Tip: [1 pronunciation tip for this topic]</i>\n\n"
        "Reply in the comments with your recording! 🎙️\n\n"
        "Output only this format, nothing else.",
        max_tokens=400,
    )


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

TRIGGER_WORDS = [
    "pronounce", "pronunciation", "вимов", "як вимовляти", "як читати",
    "ipa", "sound", "звук", "accent", "акцент", "speak", "говори",
    "how to say", "як сказати",
]


def _is_speak_trigger(text: str) -> bool:
    t = text.lower()
    return any(w in t for w in TRIGGER_WORDS)


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != "private":
        return
    await update.message.reply_html(
        "🎤 <b>Привіт! Я SpeakBetter</b> — твій тренер з вимови.\n\n"
        "Я можу:\n"
        "• Пояснити вимову будь-якого англійського слова\n"
        "• Дати IPA транскрипцію\n"
        "• Показати типові помилки українців\n"
        "• Щодня о 21:00 — виклик для розмовної практики\n\n"
        "Просто напиши мені слово або запитання про вимову!"
    )


async def cmd_pronounce(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    args = ctx.args
    if not args:
        await update.message.reply_text("Напиши слово: /pronounce <word>\nНаприклад: /pronounce through")
        return
    word = " ".join(args)
    msg = await update.message.reply_text(f"🔍 Аналізую вимову '{word}'...")
    result = await _pronounce(word)
    await msg.edit_text(result, parse_mode="HTML")


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    user = update.effective_user
    if not user or user.is_bot:
        return

    text = update.message.text.strip()
    chat_type = update.effective_chat.type

    # In groups: only respond to triggers or mentions
    if chat_type in ("group", "supergroup"):
        me = (await ctx.bot.get_me()).username.lower()
        is_mention = f"@{me}" in text.lower()
        is_reply_to_me = (
            update.message.reply_to_message is not None
            and update.message.reply_to_message.from_user is not None
            and update.message.reply_to_message.from_user.username
            and update.message.reply_to_message.from_user.username.lower() == me
        )
        if not (is_mention or is_reply_to_me or _is_speak_trigger(text)):
            return

    # Check if it's a single word (pronunciation lookup)
    words_in_msg = text.replace("@", "").split()
    if len(words_in_msg) <= 2 and all(w.isalpha() for w in words_in_msg):
        word = " ".join(words_in_msg)
        msg = await update.message.reply_text(f"🔍 Вимова '{word}'...")
        result = await _pronounce(word)
        await msg.edit_text(result, parse_mode="HTML")
    else:
        # General pronunciation question
        reply = await _ai(text)
        await update.message.reply_html(reply)


# ---------------------------------------------------------------------------
# Voice message handler
# ---------------------------------------------------------------------------

async def handle_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Process voice messages - transcribe and give pronunciation feedback"""
    if not update.message or not update.message.voice:
        return

    await update.message.reply_text("🎧 Слухаю... одну секунду!")

    try:
        import tempfile, openai

        # Download voice file
        voice = update.message.voice
        file = await ctx.bot.get_file(voice.file_id)

        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            await file.download_to_drive(tmp.name)
            tmp_path = tmp.name

        # Transcribe with Whisper
        client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        with open(tmp_path, "rb") as audio_file:
            transcript = await client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="en"
            )

        import os as _os
        _os.unlink(tmp_path)

        text = transcript.text.strip()
        if not text:
            await update.message.reply_text("😕 Не вдалося розпізнати мовлення. Спробуй ще раз, чіткіше.")
            return

        # Get pronunciation feedback via GPT
        feedback_prompt = f"""The user said: "{text}"

Give pronunciation feedback for a Ukrainian English learner:
1. What they said (transcription)
2. Likely pronunciation issues (2-3 specific tips)
3. IPA for difficult words
4. One encouragement

Keep it short (4-6 lines). Use emojis. Reply in Ukrainian."""

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": feedback_prompt}],
            max_tokens=200
        )

        feedback = response.choices[0].message.content

        await update.message.reply_text(
            f"🗣️ <b>Ти сказав:</b> «{text}»\n\n{feedback}",
            parse_mode="HTML"
        )

    except Exception as e:
        await update.message.reply_text(
            "😕 Не вдалося обробити голосове. Напиши слово текстом і я допоможу з вимовою!"
        )


# ---------------------------------------------------------------------------
# Scheduled: 21:00 daily speaking challenge
# ---------------------------------------------------------------------------

async def _speaking_challenge_loop(app: Application) -> None:
    sent_today = False
    while True:
        now = datetime.now(KYIV)
        if now.hour == 21 and now.minute == 0 and not sent_today:
            try:
                text = await _speaking_challenge()
                await app.bot.send_message(
                    chat_id=CHAT_ID,
                    text=text,
                    parse_mode="HTML",
                )
                log.info("Speaking challenge sent at 21:00")
                sent_today = True
            except Exception as exc:
                log.error("Speaking challenge failed: %s", exc)
        # Reset at midnight
        if now.hour == 0:
            sent_today = False
        await asyncio.sleep(55)  # check every ~1 min


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    app = Application.builder().token(SPEAK_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("pronounce", cmd_pronounce))
    app.add_handler(CommandHandler("say",       cmd_pronounce))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    log.info("speak_bot (@SpeakBetterrbot) online — posting challenges to chat_id=%d", CHAT_ID)

    asyncio.create_task(_speaking_challenge_loop(app))
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
