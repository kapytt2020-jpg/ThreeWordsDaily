"""
learning_bot.py — ThreeWordsDaily production bot (merged, clean version).

Environment variables (all read from .env):
  LEARNING_BOT_TOKEN   — bot token (alias for TELEGRAM_BOT_TOKEN, see .env)
  TELEGRAM_CHAT_ID     — group/channel ID for scheduled posts
  ADMIN_CHAT_ID        — admin's Telegram user ID
  OPENAI_API_KEY       — OpenAI secret key
  SHEETS_API_URL       — optional Google Sheets proxy URL (may be blank)

Run:
  python3 learning_bot.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import aiohttp
from dotenv import load_dotenv
from openai import AsyncOpenAI
from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Poll,
    Update,
)
from telegram.constants import ParseMode
from telegram.error import Forbidden, TelegramError
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)

import database

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("learning_bot")

# ---------------------------------------------------------------------------
# Configuration (module-level constants)
# ---------------------------------------------------------------------------

load_dotenv()

# LEARNING_BOT_TOKEN is the canonical name; fall back to TELEGRAM_BOT_TOKEN
# so the existing .env entry keeps working without changes.
LEARNING_BOT_TOKEN: str = (
    os.environ.get("LEARNING_BOT_TOKEN")
    or os.environ.get("TELEGRAM_BOT_TOKEN", "")
)
if not LEARNING_BOT_TOKEN:
    raise RuntimeError("LEARNING_BOT_TOKEN (or TELEGRAM_BOT_TOKEN) is not set in .env")

OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
TELEGRAM_CHAT_ID: int = int(os.environ.get("TELEGRAM_CHAT_ID", "0"))
ADMIN_CHAT_ID: int = int(os.environ.get("ADMIN_CHAT_ID", "0"))
SHEETS_API_URL: str = os.environ.get("SHEETS_API_URL", "").strip()

UKRAINE_TZ = ZoneInfo("Europe/Kyiv")
OPENAI_MODEL = "gpt-4o-mini"

WORD_GEN_SYSTEM = (
    "You are an English teacher. Generate a word appropriate for {level} level. "
    "Format: word | transcription | Ukrainian translation | example sentence | Ukrainian example"
)

FALLBACK_WORD = {
    "word": "resilient",
    "transcription": "/rɪˈzɪliənt/",
    "translation": "стійкий, витривалий",
    "example": "She remained resilient despite all the challenges.",
    "example_ua": "Вона залишалась стійкою попри всі труднощі.",
}

LEVELS: list[str] = ["A1", "A2", "B1", "B2"]

TOPIC_NAMES: dict[str, str] = {
    "work": "Робота та бізнес",
    "travel": "Подорожі",
    "everyday": "Повсякденне",
    "emotions": "Емоції",
    "technology": "Технології",
    "mixed": "Різні теми",
}

XP_WORD = 15
XP_QUIZ_CORRECT = 10
XP_LESSON = 20
XP_SAVE = 5
XP_REVIEW = 10

# ---------------------------------------------------------------------------
# OpenAI client
# ---------------------------------------------------------------------------

_openai: AsyncOpenAI = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ---------------------------------------------------------------------------
# Rank helpers
# ---------------------------------------------------------------------------

def get_rank_label(xp: int) -> str:
    if xp >= 1000:
        return "👑 Майстер"
    if xp >= 500:
        return "💎 Експерт"
    if xp >= 200:
        return "🔥 Практик"
    if xp >= 50:
        return "⚡ Учень"
    return "🌱 Новачок"


def get_rank_next_xp(xp: int) -> int:
    thresholds = [50, 200, 500, 1000, 9999]
    for t in thresholds:
        if xp < t:
            return t
    return 9999


def xp_bar(xp: int) -> str:
    filled = min(10, xp // 50)
    return "🟧" * filled + "⬜" * (10 - filled) + f" {xp} XP"


def streak_display(n: int) -> str:
    return f"🔥 {n} день поспіль" if n else "Немає серії"


# ---------------------------------------------------------------------------
# Streak logic (spec: +1 if yesterday, reset to 1 otherwise, unchanged if today)
# ---------------------------------------------------------------------------

def compute_new_streak(last_lesson_date: Optional[str], current_streak: int) -> tuple[int, bool]:
    """Return (new_streak, changed). Unchanged if already today."""
    today = str(date.today())
    yesterday = str(date.today() - timedelta(days=1))
    if last_lesson_date == today:
        return current_streak, False
    if last_lesson_date == yesterday:
        return current_streak + 1, True
    return 1, True


# ---------------------------------------------------------------------------
# DB helpers (thin wrappers so all db calls stay in one place)
# ---------------------------------------------------------------------------

async def db_get_user(tg_id: int, first_name: str = "", username: str = "") -> dict:
    return await database.get_or_create_user(tg_id, first_name, username)


async def db_update_user(tg_id: int, **fields: object) -> None:
    await database.update_user(tg_id, **fields)


async def db_add_xp(tg_id: int, xp_delta: int) -> int:
    """Add XP, persist, return new total."""
    user = await database.get_user(tg_id)
    if user is None:
        return 0
    new_xp = (user.get("xp") or 0) + xp_delta
    await database.update_user(tg_id, xp=new_xp)
    return new_xp


async def db_words_learned(tg_id: int) -> list[str]:
    user = await database.get_user(tg_id)
    if user is None:
        return []
    raw = user.get("words_learned") or "[]"
    try:
        return json.loads(raw) if isinstance(raw, str) else (raw or [])
    except (json.JSONDecodeError, TypeError):
        return []


async def db_set_words_learned(tg_id: int, words: list[str]) -> None:
    await database.update_user(tg_id, words_learned=json.dumps(words))


# ---------------------------------------------------------------------------
# Google Sheets (non-blocking, best-effort)
# ---------------------------------------------------------------------------

async def sheets_update_user(user: dict) -> None:
    """Fire-and-forget write to Google Sheets proxy. Logs warning on failure."""
    if not SHEETS_API_URL:
        return
    words_raw = user.get("words_learned") or "[]"
    try:
        words_count = len(json.loads(words_raw) if isinstance(words_raw, str) else (words_raw or []))
    except (json.JSONDecodeError, TypeError):
        words_count = 0
    payload = {
        "user_id": user.get("tg_id"),
        "username": user.get("username", ""),
        "first_name": user.get("first_name", ""),
        "level": user.get("level", ""),
        "xp": user.get("xp", 0),
        "streak": user.get("streak", 0),
        "words_learned": words_count,
        "last_active": str(date.today()),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
            async with session.post(SHEETS_API_URL, json=payload) as resp:
                if resp.status >= 400:
                    log.warning("Sheets API returned %s", resp.status)
    except Exception as exc:
        log.warning("Sheets update failed (continuing): %s", exc)


async def persist_xp_and_sync(tg_id: int, xp_delta: int) -> int:
    """Add XP, save to DB, then fire-and-forget sync to Sheets. Returns new XP."""
    new_xp = await db_add_xp(tg_id, xp_delta)
    user = await database.get_user(tg_id)
    if user:
        asyncio.create_task(sheets_update_user(user))
    return new_xp


# ---------------------------------------------------------------------------
# OpenAI helpers
# ---------------------------------------------------------------------------

async def ai_generate_word(level: str) -> dict:
    """
    Returns dict with keys: word, transcription, translation, example, example_ua.
    Falls back to FALLBACK_WORD on any OpenAI error.
    """
    prompt = WORD_GEN_SYSTEM.format(level=level)
    try:
        resp = await _openai.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": "Generate one word now."},
            ],
            max_tokens=200,
            temperature=0.8,
        )
        raw = resp.choices[0].message.content.strip()
        parts = [p.strip() for p in raw.split("|")]
        if len(parts) >= 5:
            return {
                "word": parts[0],
                "transcription": parts[1],
                "translation": parts[2],
                "example": parts[3],
                "example_ua": parts[4],
            }
        log.warning("Unexpected word format from OpenAI: %r", raw)
    except Exception as exc:
        log.error("OpenAI word generation failed: %s", exc)
    return dict(FALLBACK_WORD)


async def ai_generate_lesson(level: str, topic: str) -> dict:
    """
    Returns a lesson dict with keys: words (list of 3), idiom, mini_story, mini_story_ua.
    Raises on failure so callers can catch.
    """
    topic_ua = TOPIC_NAMES.get(topic, topic)
    system_msg = (
        "Ти вчитель англійської для українців. "
        "Відповідай ТІЛЬКИ валідним JSON без markdown та ``` блоків."
    )
    user_msg = (
        f"Створи урок англійської.\nРівень: {level}\nТема: {topic_ua}\n\n"
        "Поверни ТІЛЬКИ JSON:\n"
        "{\n"
        '  "words": [\n'
        '    {"word": "ambitious", "transcription": "/æmˈbɪʃəs/", '
        '"translation": "амбітний", "example": "She is very ambitious.", '
        '"example_ua": "Вона дуже амбітна."}\n'
        "  ],\n"
        '  "idiom": {"text": "go the extra mile", "translation": "докласти зусиль", '
        '"example": "He always goes the extra mile.", "example_ua": "Він завжди старається."},\n'
        '  "mini_story": "Short 2-3 sentence story using all 3 words.",\n'
        '  "mini_story_ua": "Переклад story українською."\n'
        "}\n"
        f"Рівно 3 слова, тема: {topic_ua}, рівень {level}."
    )
    resp = await _openai.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=900,
        temperature=0.7,
    )
    raw = resp.choices[0].message.content.strip()
    # Strip accidental markdown fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw.strip())


async def ai_quiz_from_words(words: list[dict]) -> list[dict]:
    """
    Build a 4-option multiple-choice quiz from a list of word dicts.
    Each question: question text, 4 answers, correct index (0-based).
    """
    wrong_pool = [
        "втомлений", "сміливий", "щасливий", "серйозний", "спокійний",
        "розчарований", "цікавий", "складний", "дружній", "активний",
        "ефективний", "важкий", "веселий", "сумний", "розумний", "тихий",
    ]
    questions: list[dict] = []
    for w in words:
        candidates = [x for x in wrong_pool if x != w["translation"]]
        wrongs = random.sample(candidates, min(3, len(candidates)))
        answers = [w["translation"]] + wrongs
        random.shuffle(answers)
        questions.append({
            "question": f'Що означає "{w["word"]}" {w["transcription"]}?',
            "answers": answers,
            "correct": answers.index(w["translation"]),
            "word": w["word"],
        })
    return questions


async def ai_generate_group_quiz() -> dict:
    """
    Returns a single quiz question dict for the group poll.
    Keys: question, options (list[str]), correct (int index), explanation (str).
    Falls back to a hardcoded question on failure.
    """
    raw_prompt = (
        "Поверни ТІЛЬКИ JSON без markdown:\n"
        '{"question":"[питання про англійське слово]",'
        '"options":["[правильна відповідь]","[неправильна 1]","[неправильна 2]","[неправильна 3]"],'
        '"explanation":"[пояснення 1-2 речення]"}\n'
        "Всі 4 варіанти ОДНІЄЮ мовою (українською або англійською)."
    )
    try:
        resp = await _openai.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": raw_prompt}],
            max_tokens=300,
            temperature=0.7,
        )
        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw.strip())
        opts: list[str] = data["options"][:]
        correct_answer: str = opts[0]
        random.shuffle(opts)
        return {
            "question": data["question"],
            "options": opts,
            "correct": opts.index(correct_answer),
            "explanation": data.get("explanation", ""),
        }
    except Exception as exc:
        log.error("Group quiz generation failed: %s", exc)
        return {
            "question": "Що означає 'resilient'?",
            "options": ["стійкий", "розумний", "швидкий", "сильний"],
            "correct": 0,
            "explanation": "Resilient — стійкий, витривалий до труднощів.",
        }


# ---------------------------------------------------------------------------
# Keyboards
# ---------------------------------------------------------------------------

def kb_level_select() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 A1 — Початківець",     callback_data="level_A1")],
        [InlineKeyboardButton("🔵 A2 — Базовий",         callback_data="level_A2")],
        [InlineKeyboardButton("🟡 B1 — Середній",        callback_data="level_B1")],
        [InlineKeyboardButton("🟠 B2 — Вище середнього", callback_data="level_B2")],
    ])


def kb_topic_select() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💼 Робота та бізнес", callback_data="topic_work"),
            InlineKeyboardButton("✈️ Подорожі",         callback_data="topic_travel"),
        ],
        [
            InlineKeyboardButton("💬 Повсякденне",       callback_data="topic_everyday"),
            InlineKeyboardButton("❤️ Емоції",            callback_data="topic_emotions"),
        ],
        [
            InlineKeyboardButton("💻 Технології",        callback_data="topic_technology"),
            InlineKeyboardButton("🎲 Мікс",              callback_data="topic_mixed"),
        ],
    ])


def kb_lesson_actions() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🧠 Тест",           callback_data="quiz_now"),
            InlineKeyboardButton("✅ Вивчив! +20 XP", callback_data="mark_learned"),
        ],
        [
            InlineKeyboardButton("⏭ Наступний урок",  callback_data="next_lesson"),
        ],
    ])


def kb_word_actions() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Зрозуміло! +10 XP", callback_data="word_got_it"),
            InlineKeyboardButton("➡️ Ще слово",          callback_data="word_next"),
        ],
    ])


def kb_after_quiz() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📚 Новий урок",  callback_data="next_lesson"),
            InlineKeyboardButton("📊 Мій профіль", callback_data="show_profile"),
        ],
        [
            InlineKeyboardButton("🔄 Ще раз тест", callback_data="quiz_now"),
        ],
    ])


def kb_profile_nav() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏆 Рейтинг", callback_data="show_top")],
    ])


# ---------------------------------------------------------------------------
# In-memory quiz sessions {tg_id: {...}}
# ---------------------------------------------------------------------------

_quiz_sessions: dict[int, dict] = {}


def _quiz_session(tg_id: int) -> dict:
    if tg_id not in _quiz_sessions:
        _quiz_sessions[tg_id] = {}
    return _quiz_sessions[tg_id]


# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None:
        return
    tg_id = user.id
    first_name = user.first_name or "Друже"
    username = user.username or ""

    try:
        u = await db_get_user(tg_id, first_name, username)
    except Exception as exc:
        log.error("DB error in /start: %s", exc)
        await update.message.reply_text("Щось пішло не так, спробуй ще раз.")
        return

    # Referral handling via deep link (?start=ref_<id>)
    args = ctx.args or []
    if args and args[0].startswith("ref_"):
        await _handle_referral(tg_id, args[0], u, first_name, ctx)

    level = u.get("level")

    if not level:
        # New user — ask level
        text = (
            f"👋 Привіт, <b>{first_name}</b>!\n\n"
            "Я — <b>ThreeWordsDaily</b> — твій AI-вчитель англійської.\n\n"
            "Щодня:\n"
            "• 3 нових слова + idiom + mini story\n"
            "• Тести та повторення\n"
            "• XP, серії та лідерборд\n\n"
            "Спочатку — твій рівень англійської:"
        )
        await update.message.reply_html(text, reply_markup=kb_level_select())
    else:
        # Returning user — show welcome back
        xp = u.get("xp", 0)
        streak = u.get("streak", 0)
        words = await db_words_learned(tg_id)
        rank = get_rank_label(xp)
        text = (
            f"👋 З поверненням, <b>{first_name}</b>!\n\n"
            f"{rank} · {xp_bar(xp)}\n"
            f"{streak_display(streak)}\n"
            f"📖 Слів вивчено: <b>{len(words)}</b>\n\n"
            f"Рівень: <b>{level}</b>\n\n"
            f"Скористайся командами нижче або /lessons щоб отримати урок дня!"
        )
        await update.message.reply_html(text)


async def _handle_referral(
    tg_id: int,
    ref_arg: str,
    new_user: dict,
    first_name: str,
    ctx: ContextTypes.DEFAULT_TYPE,
) -> None:
    try:
        ref_id = int(ref_arg.replace("ref_", ""))
    except ValueError:
        return
    if ref_id == tg_id:
        return
    # Only process if this user has no referrer yet
    if new_user.get("referrer_id"):
        return
    try:
        await db_update_user(tg_id, referrer_id=ref_id)
        # +25 XP to referrer
        await persist_xp_and_sync(ref_id, 25)
        await ctx.bot.send_message(
            ref_id,
            f"🎉 Твій друг <b>{first_name}</b> приєднався за твоїм посиланням!\n"
            f"+25 XP нараховано! 🚀",
            parse_mode=ParseMode.HTML,
        )
    except Exception as exc:
        log.warning("Referral handling error: %s", exc)


# ---------------------------------------------------------------------------
# /help
# ---------------------------------------------------------------------------

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_html(
        "📚 <b>Команди бота</b>\n"
        "━━━━━━━━━━━━━━━\n"
        "/start — онбординг, вибір рівня\n"
        "/word — слово дня для твого рівня (+15 XP)\n"
        "/quiz — тест з останніх слів (+10 XP за правильну)\n"
        "/lessons — повний урок: 3 слова + idiom + story (+20 XP)\n"
        "/stats — XP, серія, рівень, слів вивчено, ранг\n"
        "/profile — повний профіль з XP-баром і значками\n"
        "/top — топ-10 гравців за XP\n"
        "/save [слово] — зберегти слово у словник (+5 XP)\n"
        "/review — повторити 5 останніх збережених слів\n"
        "/mywords — список збережених слів (з пагінацією)\n"
        "/invite — реферальне посилання\n"
        "❄️ /freeze — Купити заморозку стріку (15 ⭐)\n"
        "/help — цей список\n\n"
        "💬 Напиши будь-яке слово англійською — поясню!"
    )


# ---------------------------------------------------------------------------
# /word
# ---------------------------------------------------------------------------

async def cmd_word(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    tg_id = user.id
    first_name = user.first_name or ""

    try:
        u = await db_get_user(tg_id, first_name, user.username or "")
    except Exception as exc:
        log.error("DB error in /word: %s", exc)
        await update.message.reply_text("Щось пішло не так, спробуй ще раз.")
        return

    level = u.get("level") or "B1"
    wait = await update.message.reply_text("⏳ Генерую слово...")

    try:
        w = await ai_generate_word(level)
    except Exception as exc:
        log.error("Word generation error: %s", exc)
        w = dict(FALLBACK_WORD)

    text = (
        f"🔤 <b>Слово дня</b> [{level}]\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"<b>{w['word']}</b> <code>{w['transcription']}</code>\n"
        f"🇺🇦 {w['translation']}\n\n"
        f"💬 {w['example']}\n"
        f"<i>{w['example_ua']}</i>\n\n"
        f"<i>+{XP_WORD} XP нараховано</i>"
    )

    try:
        new_xp = await persist_xp_and_sync(tg_id, XP_WORD)
        await database.add_progress_event(tg_id, "word", XP_WORD)
    except Exception as exc:
        log.error("XP update error in /word: %s", exc)
        new_xp = u.get("xp", 0)

    await wait.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb_word_actions())


# ---------------------------------------------------------------------------
# /quiz
# ---------------------------------------------------------------------------

async def cmd_quiz(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    tg_id = user.id

    try:
        u = await db_get_user(tg_id, user.first_name or "", user.username or "")
    except Exception as exc:
        log.error("DB error in /quiz: %s", exc)
        await update.message.reply_text("Щось пішло не так, спробуй ще раз.")
        return

    words = await db_words_learned(tg_id)
    # Generate quiz from stored word list or fall back to AI
    if len(words) >= 4:
        sample_words = random.sample(words, min(4, len(words)))
        questions = [
            {
                "question": f'Яке слово ти вивчав/ла?',
                "answers": _shuffle_with_correct(sample_words, w),
                "correct": 0,  # will be set properly below
                "word": w,
            }
            for w in sample_words
        ]
        # Fix correct index after shuffling
        questions = []
        for w in sample_words:
            others = [x for x in words if x != w]
            wrongs = random.sample(others, min(3, len(others)))
            while len(wrongs) < 3:
                wrongs.append("—")
            answers = [w] + wrongs
            random.shuffle(answers)
            questions.append({
                "question": f"Яке слово означає: <b>{w}</b>?",
                "answers": answers,
                "correct": answers.index(w),
                "word": w,
            })
    else:
        # Not enough saved words — use AI-generated word questions
        level = u.get("level") or "B1"
        wait = await update.message.reply_text("⏳ Генерую тест...")
        generated = []
        for _ in range(4):
            wd = await ai_generate_word(level)
            generated.append(wd)
        questions = await ai_quiz_from_words(generated)
        await wait.delete()

    session = _quiz_session(tg_id)
    session["questions"] = questions
    session["index"] = 0
    session["score"] = 0
    session["source"] = "quiz_cmd"

    await _send_quiz_question(update.effective_chat.id, tg_id, ctx)


def _shuffle_with_correct(pool: list[str], correct: str) -> list[str]:
    others = [x for x in pool if x != correct]
    wrongs = random.sample(others, min(3, len(others)))
    answers = [correct] + wrongs
    random.shuffle(answers)
    return answers


async def _send_quiz_question(
    chat_id: int,
    tg_id: int,
    ctx: ContextTypes.DEFAULT_TYPE,
    edit_message=None,
) -> None:
    session = _quiz_session(tg_id)
    questions: list[dict] = session.get("questions", [])
    idx: int = session.get("index", 0)

    if idx >= len(questions):
        await _finish_quiz(chat_id, tg_id, ctx, edit_message)
        return

    q = questions[idx]
    text = f"🧠 <b>Питання {idx + 1}/{len(questions)}</b>\n\n{q['question']}"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(ans, callback_data=f"qa_{i}")]
        for i, ans in enumerate(q["answers"])
    ])

    if edit_message:
        await edit_message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await ctx.bot.send_message(chat_id, text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def _finish_quiz(
    chat_id: int,
    tg_id: int,
    ctx: ContextTypes.DEFAULT_TYPE,
    edit_message=None,
) -> None:
    session = _quiz_session(tg_id)
    score: int = session.get("score", 0)
    total: int = len(session.get("questions", []))
    xp_earned = score * XP_QUIZ_CORRECT

    try:
        new_xp = await persist_xp_and_sync(tg_id, xp_earned)
        u = await database.get_user(tg_id)
        old_quizzes = (u or {}).get("total_quizzes", 0)
        old_correct = (u or {}).get("correct_answers", 0)
        await db_update_user(
            tg_id,
            total_quizzes=old_quizzes + 1,
            correct_answers=old_correct + score,
        )
        await database.add_progress_event(tg_id, "quiz", xp_earned)
    except Exception as exc:
        log.error("XP update error in quiz finish: %s", exc)
        new_xp = xp_earned

    stars = "⭐" * score + "☆" * (total - score)
    text = (
        f"🏁 <b>Тест завершено!</b>\n\n"
        f"{stars}\n"
        f"Правильно: <b>{score}/{total}</b>\n"
        f"Зароблено: <b>+{xp_earned} XP</b> 🎉\n"
        f"Всього XP: <b>{new_xp}</b>"
    )

    if edit_message:
        await edit_message.edit_text(
            text, parse_mode=ParseMode.HTML, reply_markup=kb_after_quiz()
        )
    else:
        await ctx.bot.send_message(
            chat_id, text, parse_mode=ParseMode.HTML, reply_markup=kb_after_quiz()
        )

    _quiz_sessions.pop(tg_id, None)


# ---------------------------------------------------------------------------
# /stats
# ---------------------------------------------------------------------------

async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    tg_id = user.id

    try:
        u = await db_get_user(tg_id, user.first_name or "", user.username or "")
        stats = await database.get_user_stats(tg_id)
    except Exception as exc:
        log.error("DB error in /stats: %s", exc)
        await update.message.reply_text("Щось пішло не так, спробуй ще раз.")
        return

    xp = u.get("xp", 0)
    streak = u.get("streak", 0)
    level = u.get("level") or "—"
    words_count = stats.get("words_learned_count", 0)
    rank_pos = stats.get("rank", "?")
    rank_label = get_rank_label(xp)
    next_xp = get_rank_next_xp(xp)
    total_lessons = u.get("total_lessons", 0)
    total_quizzes = u.get("total_quizzes", 0)

    text = (
        f"📊 <b>Статистика {user.first_name}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Рівень: <b>{level}</b>\n"
        f"Ранг: {rank_label}\n"
        f"XP: {xp_bar(xp)}\n"
        f"До наступного рангу: <b>{max(0, next_xp - xp)} XP</b>\n"
        f"{streak_display(streak)}\n"
        f"📖 Слів вивчено: <b>{words_count}</b>\n"
        f"📚 Уроків: <b>{total_lessons}</b>\n"
        f"🧠 Тестів: <b>{total_quizzes}</b>\n"
        f"🏆 Місце в рейтингу: <b>#{rank_pos}</b>"
    )
    await update.message.reply_html(text)


# ---------------------------------------------------------------------------
# /profile
# ---------------------------------------------------------------------------

BADGE_DEFINITIONS: list[tuple[str, str]] = [
    ("first_word",   "🌱 Перше слово"),
    ("streak_3",     "🔥 3 дні поспіль"),
    ("streak_7",     "💎 Тиждень!"),
    ("xp_50",        "⚡ 50 XP"),
    ("xp_100",       "🏆 100 XP"),
    ("xp_500",       "👑 500 XP"),
    ("words_10",     "📚 10 слів"),
    ("words_50",     "🎓 50 слів"),
    ("lessons_10",   "📖 10 уроків"),
]


async def cmd_profile(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    tg_id = user.id

    try:
        u = await db_get_user(tg_id, user.first_name or "", user.username or "")
        rewards = await database.get_rewards(tg_id)
        stats = await database.get_user_stats(tg_id)
    except Exception as exc:
        log.error("DB error in /profile: %s", exc)
        await update.message.reply_text("Щось пішло не так, спробуй ще раз.")
        return

    xp = u.get("xp", 0)
    streak = u.get("streak", 0)
    level = u.get("level") or "—"
    words = await db_words_learned(tg_id)
    total_lessons = u.get("total_lessons", 0)
    rank_label = get_rank_label(xp)
    next_xp = get_rank_next_xp(xp)
    rank_pos = stats.get("rank", "?")

    # XP bar (percentage to next rank)
    current_floor = {50: 0, 200: 50, 500: 200, 1000: 500, 9999: 1000}.get(next_xp, 0)
    progress_range = next_xp - current_floor
    progress_filled = xp - current_floor
    bar_filled = min(10, int(progress_filled / progress_range * 10)) if progress_range > 0 else 10
    bar = "🟧" * bar_filled + "⬜" * (10 - bar_filled)

    # Earned badge IDs
    earned_ids = {r["badge_id"] for r in rewards}
    badges_text = " ".join(label for bid, label in BADGE_DEFINITIONS if bid in earned_ids)

    # Companion stage
    companion_stages = ["🥚 Яйце", "🐣 Малюк", "🌟 Дух слів", "🦋 Мудрець", "🔮 Легенда", "⚡ Хаос"]
    stage = min(5, len(words) // 10)
    companion = companion_stages[stage]

    # Streak calendar (last 7 days)
    last_lesson = u.get("last_lesson_date")
    cal = _streak_calendar(streak, last_lesson)

    text = (
        f"👤 <b>Профіль {user.first_name}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Рівень: <b>{level}</b>  |  {rank_label}\n\n"
        f"XP: <b>{xp}</b>\n"
        f"{bar} → <b>{next_xp} XP</b>\n\n"
        f"Серія: {cal}\n"
        f"📖 Слів вивчено: <b>{len(words)}</b>\n"
        f"📚 Уроків: <b>{total_lessons}</b>\n"
        f"🏆 Місце: <b>#{rank_pos}</b>\n\n"
        f"Компаньйон: {companion}\n"
    )
    if badges_text:
        text += f"\nЗначки: {badges_text}\n"

    await update.message.reply_html(text, reply_markup=kb_profile_nav())

    # Check and award new badges (non-blocking side-effect)
    asyncio.create_task(_check_and_award_badges(tg_id, u, len(words)))


def _streak_calendar(streak: int, last_lesson_date: Optional[str]) -> str:
    today = date.today()
    days: list[str] = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        # A day is "active" if it's within the current streak window
        days_ago = i
        if streak >= (days_ago + 1) and last_lesson_date:
            days.append("🟧")
        else:
            days.append("⬜")
    return "".join(days) + f" {streak}🔥"


async def _check_and_award_badges(tg_id: int, user: dict, words_count: int) -> None:
    xp = user.get("xp", 0)
    streak = user.get("streak", 0)
    total_lessons = user.get("total_lessons", 0)

    checks: list[tuple[str, bool]] = [
        ("first_word",  words_count >= 1),
        ("streak_3",    streak >= 3),
        ("streak_7",    streak >= 7),
        ("xp_50",       xp >= 50),
        ("xp_100",      xp >= 100),
        ("xp_500",      xp >= 500),
        ("words_10",    words_count >= 10),
        ("words_50",    words_count >= 50),
        ("lessons_10",  total_lessons >= 10),
    ]
    try:
        for badge_id, earned in checks:
            if earned:
                await database.add_reward(tg_id, badge_id)
    except Exception as exc:
        log.warning("Badge check error: %s", exc)


# ---------------------------------------------------------------------------
# /lessons
# ---------------------------------------------------------------------------

async def cmd_lessons(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    tg_id = user.id

    try:
        u = await db_get_user(tg_id, user.first_name or "", user.username or "")
    except Exception as exc:
        log.error("DB error in /lessons: %s", exc)
        await update.message.reply_text("Щось пішло не так, спробуй ще раз.")
        return

    level = u.get("level") or "B1"
    topic = u.get("topic") or "everyday"

    wait = await update.message.reply_text("⏳ AI генерує урок...")
    await _deliver_lesson(tg_id, level, topic, u, ctx, wait_msg=wait)


async def _deliver_lesson(
    tg_id: int,
    level: str,
    topic: str,
    user_row: dict,
    ctx: ContextTypes.DEFAULT_TYPE,
    wait_msg=None,
    edit_msg=None,
) -> None:
    """Generate and send/edit a lesson. Updates streak and XP."""
    today = str(date.today())

    # Check lesson cache first
    lesson: Optional[dict] = await database.get_cached_lesson(level, topic, today)
    if lesson is None:
        try:
            lesson = await ai_generate_lesson(level, topic)
            await database.cache_lesson(level, topic, today, json.dumps(lesson))
        except Exception as exc:
            log.error("Lesson generation failed: %s", exc)
            err = "Не вдалось згенерувати урок. Спробуй /lessons ще раз."
            if wait_msg:
                await wait_msg.edit_text(err)
            elif edit_msg:
                await edit_msg.edit_text(err)
            return

    # Streak + XP
    last_date = user_row.get("last_lesson_date")
    current_streak = user_row.get("streak", 0)
    new_streak, streak_changed = compute_new_streak(last_date, current_streak)

    try:
        update_fields: dict = {"total_lessons": (user_row.get("total_lessons") or 0) + 1}
        if streak_changed:
            update_fields["streak"] = new_streak
            update_fields["last_lesson_date"] = today
        await db_update_user(tg_id, **update_fields)
        new_xp = await persist_xp_and_sync(tg_id, XP_LESSON)
        await database.add_progress_event(tg_id, "lesson", XP_LESSON)
    except Exception as exc:
        log.error("XP/streak update error in lesson: %s", exc)
        new_xp = (user_row.get("xp") or 0) + XP_LESSON

    # Notify referrer when their invitee completes first lesson
    import aiosqlite
    _db_path = getattr(database, "DB_PATH", None) or os.path.join(os.path.dirname(os.path.abspath(__file__)), "miniapp", "threewords.db")
    try:
        async with aiosqlite.connect(_db_path) as _db:
            _db.row_factory = aiosqlite.Row
            user_row_ref = await (await _db.execute(
                "SELECT referrer_id, total_lessons FROM users WHERE tg_id=?", (tg_id,)
            )).fetchone()
            if user_row_ref and user_row_ref["referrer_id"] and user_row_ref["total_lessons"] == 1:
                referrer_id = user_row_ref["referrer_id"]
                # Give referrer bonus XP
                await _db.execute(
                    "UPDATE users SET xp = xp + 100, weekly_xp = COALESCE(weekly_xp, 0) + 100 WHERE tg_id=?",
                    (referrer_id,)
                )
                await _db.commit()
                # Notify referrer
                try:
                    await ctx.bot.send_message(
                        chat_id=referrer_id,
                        text=f"🎉 Твій запрошений друг пройшов перший урок!\n\n+100 XP на твій рахунок 🏆"
                    )
                except Exception:
                    pass
    except Exception as exc:
        log.warning("Referral first-lesson notification failed: %s", exc)

    # Format lesson text
    words_text = ""
    for i, w in enumerate(lesson.get("words", []), 1):
        words_text += (
            f"{i}. <b>{w['word']}</b> <code>{w['transcription']}</code>\n"
            f"   🇺🇦 <i>{w['translation']}</i>\n"
            f"   💬 {w['example']}\n"
            f"   <i>{w['example_ua']}</i>\n\n"
        )

    idiom = lesson.get("idiom", {})
    idiom_text = (
        f"💬 <b>Idiom дня:</b>\n"
        f"<i>{idiom.get('text', '')}</i> — {idiom.get('translation', '')}\n"
        f"💡 <i>{idiom.get('example', '')}</i>\n"
        f"<i>{idiom.get('example_ua', '')}</i>\n\n"
    )

    story_text = (
        f"📖 <b>Mini-story:</b>\n"
        f"<i>{lesson.get('mini_story', '')}</i>\n"
        f"<i>{lesson.get('mini_story_ua', '')}</i>"
    )

    text = (
        f"📚 <b>Урок дня</b> | {level} | {streak_display(new_streak)}\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"<b>Слова:</b>\n\n"
        f"{words_text}"
        f"{idiom_text}"
        f"{story_text}\n\n"
        f"<i>+{XP_LESSON} XP нараховано</i>"
    )

    # Store lesson words in session for quiz
    session = _quiz_session(tg_id)
    session["lesson_words"] = lesson.get("words", [])

    if wait_msg:
        await wait_msg.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb_lesson_actions())
    elif edit_msg:
        await edit_msg.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb_lesson_actions())


# ---------------------------------------------------------------------------
# /top
# ---------------------------------------------------------------------------

async def cmd_top(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    caller_id = update.effective_user.id
    medals = ["🥇", "🥈", "🥉", "4.", "5.", "6.", "7.", "8.", "9.", "10."]

    try:
        leaders = await database.get_leaderboard(limit=10)
    except Exception as exc:
        log.error("Leaderboard error: %s", exc)
        await update.message.reply_text("Щось пішло не так, спробуй ще раз.")
        return

    lines: list[str] = []
    for i, entry in enumerate(leaders):
        name = entry.get("first_name", "Гравець")
        xp = entry.get("xp", 0)
        streak = entry.get("streak", 0)
        me = " ← ти" if entry.get("tg_id") == caller_id else ""
        rank_label = get_rank_label(xp)
        medal = medals[i] if i < len(medals) else f"{i + 1}."
        lines.append(f"{medal} <b>{name}</b>{me}\n{rank_label} | ⭐ {xp} | 🔥 {streak}")

    body = "\n\n".join(lines) if lines else "Поки порожньо — почни навчатись! 💪"
    await update.message.reply_html(
        f"🏆 <b>Топ-10 гравців</b>\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"{body}\n\n"
        f"Навчайся щодня — потрапляй у ТОП! 🚀"
    )


# ---------------------------------------------------------------------------
# /save [word]
# ---------------------------------------------------------------------------

async def cmd_save(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    tg_id = user.id
    word_arg = " ".join(ctx.args).strip() if ctx.args else ""

    if not word_arg:
        await update.message.reply_html(
            "✏️ Використання: <code>/save слово</code>\n"
            "Наприклад: <code>/save resilient</code>"
        )
        return

    word_lower = word_arg.lower()

    try:
        await db_get_user(tg_id, user.first_name or "", user.username or "")
        words = await db_words_learned(tg_id)
    except Exception as exc:
        log.error("DB error in /save: %s", exc)
        await update.message.reply_text("Щось пішло не так, спробуй ще раз.")
        return

    if word_lower in words:
        await update.message.reply_html(
            f"📚 <b>'{word_arg}'</b> вже є у твоєму словнику!"
        )
        return

    words.append(word_lower)
    wait = await update.message.reply_text("⏳ Зберігаю...")

    try:
        await db_set_words_learned(tg_id, words)
        new_xp = await persist_xp_and_sync(tg_id, XP_SAVE)
        await database.add_progress_event(tg_id, "save_word", XP_SAVE)
    except Exception as exc:
        log.error("Save word DB error: %s", exc)
        await wait.edit_text("Щось пішло не так, спробуй ще раз.")
        return

    await wait.edit_text(
        f"✅ <b>'{word_arg}'</b> збережено у словник!\n\n"
        f"📖 Всього слів: <b>{len(words)}</b>\n"
        f"+{XP_SAVE} XP 🎯",
        parse_mode=ParseMode.HTML,
    )


# ---------------------------------------------------------------------------
# /review
# ---------------------------------------------------------------------------

async def cmd_review(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    tg_id = user.id

    try:
        await db_get_user(tg_id, user.first_name or "", user.username or "")
        words = await db_words_learned(tg_id)
    except Exception as exc:
        log.error("DB error in /review: %s", exc)
        await update.message.reply_text("Щось пішло не так, спробуй ще раз.")
        return

    if not words:
        await update.message.reply_html(
            "📚 Твій словник порожній.\n\n"
            "Збережи слова командою <code>/save слово</code> або пройди урок /lessons."
        )
        return

    sample = words[-5:]  # Last 5 saved
    lines = [f"{i + 1}. <b>{w}</b>" for i, w in enumerate(sample)]

    try:
        new_xp = await persist_xp_and_sync(tg_id, XP_REVIEW)
    except Exception as exc:
        log.error("XP update error in /review: %s", exc)
        new_xp = 0

    await update.message.reply_html(
        f"🔁 <b>Повторення — {len(sample)} з {len(words)} слів:</b>\n"
        f"━━━━━━━━━━━━━━━\n\n"
        + "\n".join(lines)
        + f"\n\n+{XP_REVIEW} XP 💡\n"
        f"Спробуй скласти речення з кожним словом!\n\n"
        f"/mywords — повний список | /save — додати слово"
    )


# ---------------------------------------------------------------------------
# /mywords
# ---------------------------------------------------------------------------

async def cmd_mywords(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    tg_id = user.id

    try:
        words = await db_words_learned(tg_id)
    except Exception as exc:
        log.error("DB error in /mywords: %s", exc)
        await update.message.reply_text("Щось пішло не так, спробуй ще раз.")
        return

    if not words:
        await update.message.reply_html(
            "📚 Словник порожній.\n"
            "<code>/save слово</code> — щоб додати!"
        )
        return

    # Show up to 20 most recent (stored in order, newest last)
    page = list(reversed(words))[:20]
    total = len(words)
    lines = [f"• <b>{w}</b>" for w in page]

    await update.message.reply_html(
        f"📚 <b>Мій словник ({total} слів):</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        + "\n".join(lines)
        + ("\n<i>…показані останні 20</i>" if total > 20 else "")
        + "\n\n/review — повторити | /save — додати"
    )


# ---------------------------------------------------------------------------
# /invite
# ---------------------------------------------------------------------------

async def cmd_invite(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    tg_id = user.id

    try:
        bot_info = await ctx.bot.get_me()
        bot_username = bot_info.username
    except Exception as exc:
        log.error("get_me failed: %s", exc)
        await update.message.reply_text("Щось пішло не так, спробуй ще раз.")
        return

    ref_link = f"https://t.me/{bot_username}?start=ref_{tg_id}"

    await update.message.reply_html(
        f"🔗 <b>Твоє реферальне посилання:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"Коли друг приєднається — ти отримаєш <b>+25 XP</b> 🚀\n"
        f"Ділись з друзями!"
    )


# ---------------------------------------------------------------------------
# Callback query handlers
# ---------------------------------------------------------------------------

async def cb_level_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    tg_id = query.from_user.id
    level = query.data.replace("level_", "")

    try:
        await db_update_user(tg_id, level=level)
    except Exception as exc:
        log.error("DB error in cb_level_select: %s", exc)
        await query.message.reply_text("Щось пішло не так, спробуй ще раз.")
        return

    await query.edit_message_text(
        f"✅ Рівень: <b>{level}</b>\n\nТепер обери тему:",
        parse_mode=ParseMode.HTML,
        reply_markup=kb_topic_select(),
    )


async def cb_topic_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    tg_id = query.from_user.id
    topic = query.data.replace("topic_", "")
    topic_label = TOPIC_NAMES.get(topic, topic)

    try:
        await db_update_user(tg_id, topic=topic)
    except Exception as exc:
        log.error("DB error in cb_topic_select: %s", exc)
        await query.message.reply_text("Щось пішло не так, спробуй ще раз.")
        return

    await query.edit_message_text(
        f"✅ Тема: <b>{topic_label}</b>\n\n"
        f"Відмінний вибір! 💪\n\n"
        f"Тепер ти готовий до навчання!\n"
        f"/lessons — перший урок\n"
        f"/word — слово дня\n"
        f"/help — всі команди",
        parse_mode=ParseMode.HTML,
    )


async def cb_word_got_it(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    tg_id = query.from_user.id
    await query.answer("+10 XP!")
    try:
        new_xp = await persist_xp_and_sync(tg_id, 10)
    except Exception as exc:
        log.error("XP error in cb_word_got_it: %s", exc)
        new_xp = 0
    await query.message.reply_html(f"✅ Слово засвоєно! +10 XP 🎯  (Всього: {new_xp})")


async def cb_word_next(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer("Генерую...")
    tg_id = query.from_user.id

    try:
        u = await database.get_user(tg_id)
        level = (u or {}).get("level") or "B1"
    except Exception:
        level = "B1"

    w = await ai_generate_word(level)
    text = (
        f"🔤 <b>Наступне слово</b> [{level}]\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"<b>{w['word']}</b> <code>{w['transcription']}</code>\n"
        f"🇺🇦 {w['translation']}\n\n"
        f"💬 {w['example']}\n"
        f"<i>{w['example_ua']}</i>"
    )
    try:
        await persist_xp_and_sync(tg_id, XP_WORD)
    except Exception as exc:
        log.warning("XP error in cb_word_next: %s", exc)

    await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb_word_actions())


async def cb_quiz_now(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer("Генерую тест...")
    tg_id = query.from_user.id

    # Use words from the last lesson session if available
    session = _quiz_session(tg_id)
    lesson_words: list[dict] = session.get("lesson_words", [])

    if lesson_words:
        questions = await ai_quiz_from_words(lesson_words)
    else:
        try:
            u = await database.get_user(tg_id)
            level = (u or {}).get("level") or "B1"
        except Exception:
            level = "B1"
        generated = []
        for _ in range(4):
            generated.append(await ai_generate_word(level))
        questions = await ai_quiz_from_words(generated)

    session["questions"] = questions
    session["index"] = 0
    session["score"] = 0

    await _send_quiz_question(query.message.chat_id, tg_id, ctx, edit_message=query.message)


async def cb_quiz_answer(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    tg_id = query.from_user.id
    answer_idx = int(query.data.replace("qa_", ""))

    session = _quiz_session(tg_id)
    questions = session.get("questions", [])
    idx = session.get("index", 0)

    if idx >= len(questions):
        await query.answer("Тест вже завершено.")
        return

    q = questions[idx]
    correct = q["correct"]
    is_correct = answer_idx == correct

    if is_correct:
        session["score"] = session.get("score", 0) + 1
        await query.answer("✅ Правильно!")
        result_text = (
            f"✅ <b>Правильно!</b>\n\n"
            f"<i>{q['answers'][correct]}</i> — вірна відповідь 🎯"
        )
    else:
        await query.answer("❌ Не вірно")
        result_text = (
            f"❌ <b>Не вірно</b>\n\n"
            f"Правильна: <i>{q['answers'][correct]}</i>\n"
            f"Не здавайся! 💪"
        )

    session["index"] = idx + 1
    next_kb = InlineKeyboardMarkup([[InlineKeyboardButton("➡️ Далі", callback_data="quiz_next")]])
    await query.message.edit_text(result_text, parse_mode=ParseMode.HTML, reply_markup=next_kb)


async def cb_quiz_next(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await _send_quiz_question(query.message.chat_id, query.from_user.id, ctx, edit_message=query.message)


async def cb_mark_learned(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    tg_id = query.from_user.id
    await query.answer("✅ +20 XP! Слова збережено!")

    session = _quiz_session(tg_id)
    lesson_words: list[dict] = session.get("lesson_words", [])

    try:
        existing = await db_words_learned(tg_id)
        new_words = [w["word"] for w in lesson_words if w["word"] not in existing]
        updated = existing + new_words
        if new_words:
            await db_set_words_learned(tg_id, updated)
        new_xp = await persist_xp_and_sync(tg_id, XP_LESSON)
        await database.add_progress_event(tg_id, "mark_learned", XP_LESSON)
    except Exception as exc:
        log.error("mark_learned DB error: %s", exc)
        new_xp = 0
        new_words = []
        updated = []

    u = await database.get_user(tg_id)
    streak = (u or {}).get("streak", 0)
    rank_label = get_rank_label(new_xp)

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏭ Наступний урок", callback_data="next_lesson"),
            InlineKeyboardButton("📊 Профіль",        callback_data="show_profile"),
        ],
        [InlineKeyboardButton("🧠 Тест",             callback_data="quiz_now")],
    ])
    await query.message.edit_text(
        f"✅ <b>Чудова робота!</b> +{XP_LESSON} XP 🎉\n\n"
        f"{rank_label}\n\n"
        f"📚 Нових слів: <b>+{len(new_words)}</b>\n"
        f"📖 Всього у словнику: <b>{len(updated)}</b>\n"
        f"⭐ XP: <b>{new_xp}</b>\n"
        f"{streak_display(streak)}",
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
    )


async def cb_next_lesson(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer("Генерую урок...")
    tg_id = query.from_user.id

    try:
        u = await database.get_user(tg_id)
        if u is None:
            u = {}
    except Exception:
        u = {}

    level = u.get("level") or "B1"
    topic = u.get("topic") or "everyday"
    await _deliver_lesson(tg_id, level, topic, u, ctx, edit_msg=query.message)


async def cb_show_profile(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    # Reuse cmd_profile logic by faking an update-like call
    user = query.from_user
    tg_id = user.id

    try:
        u = await db_get_user(tg_id, user.first_name or "", user.username or "")
        rewards = await database.get_rewards(tg_id)
        stats = await database.get_user_stats(tg_id)
    except Exception as exc:
        log.error("DB error in cb_show_profile: %s", exc)
        await query.message.reply_text("Щось пішло не так, спробуй ще раз.")
        return

    xp = u.get("xp", 0)
    streak = u.get("streak", 0)
    level = u.get("level") or "—"
    words = await db_words_learned(tg_id)
    rank_label = get_rank_label(xp)
    next_xp = get_rank_next_xp(xp)
    rank_pos = stats.get("rank", "?")
    earned_ids = {r["badge_id"] for r in rewards}
    badges_text = " ".join(label for bid, label in BADGE_DEFINITIONS if bid in earned_ids)
    companion_stages = ["🥚 Яйце", "🐣 Малюк", "🌟 Дух слів", "🦋 Мудрець", "🔮 Легенда", "⚡ Хаос"]
    companion = companion_stages[min(5, len(words) // 10)]
    last_lesson = u.get("last_lesson_date")
    cal = _streak_calendar(streak, last_lesson)

    text = (
        f"👤 <b>Профіль {user.first_name}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Рівень: <b>{level}</b>  |  {rank_label}\n"
        f"⭐ {xp_bar(xp)}\n"
        f"Серія: {cal}\n"
        f"📖 Слів: <b>{len(words)}</b>  |  🏆 #{rank_pos}\n"
        f"Компаньйон: {companion}\n"
    )
    if badges_text:
        text += f"Значки: {badges_text}\n"

    await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb_profile_nav())


async def cb_show_top(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    caller_id = query.from_user.id
    medals = ["🥇", "🥈", "🥉", "4.", "5.", "6.", "7.", "8.", "9.", "10."]

    try:
        leaders = await database.get_leaderboard(limit=10)
    except Exception as exc:
        log.error("Leaderboard error: %s", exc)
        await query.message.reply_text("Щось пішло не так, спробуй ще раз.")
        return

    lines: list[str] = []
    for i, entry in enumerate(leaders):
        name = entry.get("first_name", "Гравець")
        xp = entry.get("xp", 0)
        streak = entry.get("streak", 0)
        me = " ← ти" if entry.get("tg_id") == caller_id else ""
        medal = medals[i] if i < len(medals) else f"{i + 1}."
        lines.append(f"{medal} <b>{name}</b>{me} — ⭐{xp} | 🔥{streak}")

    body = "\n".join(lines) if lines else "Поки порожньо!"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="show_profile")]])
    await query.message.edit_text(
        f"🏆 <b>Топ-10 гравців</b>\n━━━━━━━━━━━━━━━\n\n{body}",
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
    )


# ---------------------------------------------------------------------------
# Text message handler
# ---------------------------------------------------------------------------

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    user = update.effective_user
    if user is None or user.is_bot:
        return

    msg = update.message
    text = msg.text.strip()
    tg_id = user.id
    is_group = msg.chat.type in ("group", "supergroup")

    if is_group:
        try:
            bot_info = await ctx.bot.get_me()
            bot_username = bot_info.username
        except Exception:
            return
        is_mention = f"@{bot_username}" in text
        is_reply = (
            msg.reply_to_message is not None
            and msg.reply_to_message.from_user is not None
            and msg.reply_to_message.from_user.id == ctx.bot.id
        )
        if not is_mention and not is_reply:
            return
        text = text.replace(f"@{bot_username}", "").strip()

    if not text or len(text) > 200:
        return

    # Short text = word lookup; longer = translation/question
    if len(text.split()) <= 4:
        wait = await msg.reply_text("⏳ AI пояснює...")
        try:
            resp = await _openai.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{
                    "role": "user",
                    "content": (
                        f"Поясни слово або фразу '{text}' для учня англійської. "
                        "Дай переклад та 2 приклади речень. Відповідай українською, коротко."
                    ),
                }],
                max_tokens=250,
                temperature=0.6,
            )
            explanation = resp.choices[0].message.content.strip()
        except Exception as exc:
            log.error("OpenAI text handler error: %s", exc)
            explanation = "Не вдалось отримати пояснення. Спробуй ще раз."

        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("📚 Урок дня", callback_data="next_lesson"),
            InlineKeyboardButton("🧠 Тест",     callback_data="quiz_now"),
        ]])
        await wait.edit_text(
            f"💡 <b>{text}:</b>\n\n{explanation}",
            parse_mode=ParseMode.HTML,
            reply_markup=kb,
        )
    else:
        wait = await msg.reply_text("⏳ Перекладаю...")
        try:
            resp = await _openai.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": (
                    f"Перекладаю для учня англійської:\n'{text}'\n\n"
                    "Дай переклад українською і 1-2 нотатки про граматику або вживання. Коротко."
                )}],
                max_tokens=200,
            )
            translation = resp.choices[0].message.content.strip()
        except Exception as exc:
            log.error("OpenAI translation error: %s", exc)
            translation = "Не вдалось перекласти. Спробуй ще раз."

        await wait.edit_text(f"🔤 <b>Переклад:</b>\n\n{translation}", parse_mode=ParseMode.HTML)


# ---------------------------------------------------------------------------
# Scheduled group posts  (09:00, 12:00, 20:00 Kyiv time)
# ---------------------------------------------------------------------------

async def job_morning_word(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """09:00 Kyiv — Word of the day to group."""
    if not TELEGRAM_CHAT_ID:
        log.warning("TELEGRAM_CHAT_ID not set; skipping morning word post.")
        return
    try:
        # Pick level B1 for group posts (broad audience)
        w = await ai_generate_word("B1")
        text = (
            f"🔤 <b>Слово дня</b>\n"
            f"━━━━━━━━━━━━━━━\n\n"
            f"<b>{w['word']}</b> <code>{w['transcription']}</code>\n"
            f"🇺🇦 {w['translation']}\n\n"
            f"💬 {w['example']}\n"
            f"<i>{w['example_ua']}</i>\n\n"
            f"Чи знав/ла ти це слово раніше? 👇"
        )
        await ctx.bot.send_message(TELEGRAM_CHAT_ID, text, parse_mode=ParseMode.HTML)
        log.info("Morning word post sent to group.")
    except Exception as exc:
        log.error("Morning word post failed: %s", exc)


async def job_midday_quiz(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """12:00 Kyiv — Daily quiz poll to group."""
    if not TELEGRAM_CHAT_ID:
        log.warning("TELEGRAM_CHAT_ID not set; skipping midday quiz post.")
        return
    try:
        data = await ai_generate_group_quiz()
        await ctx.bot.send_poll(
            chat_id=TELEGRAM_CHAT_ID,
            question="🧠 " + data["question"],
            options=data["options"],
            type=Poll.QUIZ,
            correct_option_id=data["correct"],
            explanation=data["explanation"] or None,
            is_anonymous=False,
        )
        log.info("Midday quiz poll sent to group.")
    except Exception as exc:
        log.error("Midday quiz post failed: %s", exc)


async def job_evening_motivation(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """20:00 Kyiv — Evening motivation + streak reminder to group."""
    if not TELEGRAM_CHAT_ID:
        log.warning("TELEGRAM_CHAT_ID not set; skipping evening motivation post.")
        return
    try:
        motivational_lines = [
            "Твоя серія чекає! Не давай їй перерватись — /lessons 🔥",
            "Ще один день — ще одне слово. Ти на вірному шляху! /word 💪",
            "Хороший вечір, щоб повторити слова. /review 📖",
            "Сьогодні ти краще, ніж учора. Підтвердь свою серію! /lessons 🚀",
            "Вечір — ідеальний час для маленького кроку. /word або /quiz 🌙",
        ]
        text = (
            f"🌙 <b>Вечірнє нагадування</b>\n\n"
            f"{random.choice(motivational_lines)}\n\n"
            f"Серія не чекає — зафіксуй сьогоднішній день! 🔥"
        )
        await ctx.bot.send_message(TELEGRAM_CHAT_ID, text, parse_mode=ParseMode.HTML)
        log.info("Evening motivation post sent to group.")
    except Exception as exc:
        log.error("Evening motivation post failed: %s", exc)


# ---------------------------------------------------------------------------
# Bot setup and main
# ---------------------------------------------------------------------------

async def post_init(application: Application) -> None:
    """Runs once after the application is built, before polling starts."""
    log.info("Initializing database...")
    try:
        await database.init_db()
        log.info("Database initialized.")
    except Exception as exc:
        log.error("DB init failed: %s", exc)

    log.info("Setting bot commands...")
    try:
        await application.bot.set_my_commands([
            BotCommand("start",   "Початок / вибір рівня"),
            BotCommand("word",    "Слово дня (+15 XP)"),
            BotCommand("lessons", "Урок дня: 3 слова + idiom (+20 XP)"),
            BotCommand("quiz",    "Тест (+10 XP за правильну)"),
            BotCommand("stats",   "Моя статистика"),
            BotCommand("profile", "Повний профіль"),
            BotCommand("top",     "Топ-10 гравців"),
            BotCommand("save",    "Зберегти слово (+5 XP)"),
            BotCommand("review",  "Повторити 5 слів (+10 XP)"),
            BotCommand("mywords", "Мій словник"),
            BotCommand("invite",  "Реферальне посилання"),
            BotCommand("help",    "Список команд"),
        ])
    except Exception as exc:
        log.error("set_my_commands failed: %s", exc)


def _register_handlers(app: Application) -> None:
    # Commands
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CommandHandler("word",    cmd_word))
    app.add_handler(CommandHandler("quiz",    cmd_quiz))
    app.add_handler(CommandHandler("stats",   cmd_stats))
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("lessons", cmd_lessons))
    app.add_handler(CommandHandler("top",     cmd_top))
    app.add_handler(CommandHandler("save",    cmd_save))
    app.add_handler(CommandHandler("review",  cmd_review))
    app.add_handler(CommandHandler("mywords", cmd_mywords))
    app.add_handler(CommandHandler("invite",      cmd_invite))
    app.add_handler(CommandHandler("subscribe",   cmd_subscribe))
    app.add_handler(CommandHandler("premium",     cmd_subscribe))
    app.add_handler(CommandHandler("freeze",      cmd_freeze))
    app.add_handler(CommandHandler("streakfreeze", cmd_freeze))
    app.add_handler(PreCheckoutQueryHandler(cb_pre_checkout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, cb_successful_payment))

    # Callback queries — specific patterns before catch-all
    app.add_handler(CallbackQueryHandler(cb_level_select,  pattern=r"^level_"))
    app.add_handler(CallbackQueryHandler(cb_topic_select,  pattern=r"^topic_"))
    app.add_handler(CallbackQueryHandler(cb_word_got_it,   pattern=r"^word_got_it$"))
    app.add_handler(CallbackQueryHandler(cb_word_next,     pattern=r"^word_next$"))
    app.add_handler(CallbackQueryHandler(cb_quiz_now,      pattern=r"^quiz_now$"))
    app.add_handler(CallbackQueryHandler(cb_quiz_answer,   pattern=r"^qa_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_quiz_next,     pattern=r"^quiz_next$"))
    app.add_handler(CallbackQueryHandler(cb_mark_learned,  pattern=r"^mark_learned$"))
    app.add_handler(CallbackQueryHandler(cb_next_lesson,   pattern=r"^next_lesson$"))
    app.add_handler(CallbackQueryHandler(cb_show_profile,  pattern=r"^show_profile$"))
    app.add_handler(CallbackQueryHandler(cb_show_top,      pattern=r"^show_top$"))

    # Text messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))


# ===== PREMIUM / TELEGRAM STARS =====

PREMIUM_STARS = 75          # 75 Stars ≈ $1.50/month
PREMIUM_CHARS = {"vex", "seraph"}   # locked behind premium
API_BASE = "http://localhost:8000"
PREMIUM_SECRET = os.getenv("PREMIUM_SECRET", "twd_premium_secret_2026")


async def cmd_freeze(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Buy streak freeze with Telegram Stars"""
    user_id = update.effective_user.id

    # Check current freezes
    import aiosqlite
    db_path = getattr(database, "DB_PATH", None) or os.path.join(os.path.dirname(os.path.abspath(__file__)), "miniapp", "threewords.db")
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        row = await (await db.execute(
            "SELECT streak_freeze, streak FROM users WHERE tg_id=?", (user_id,)
        )).fetchone()

    if row and (row["streak_freeze"] or 0) >= 3:
        await update.message.reply_text(
            "❄️ У тебе вже є 3 заморозки стріку. Використай їх перед покупкою нових!"
        )
        return

    # Send Stars invoice for freeze
    await update.message.reply_invoice(
        title="❄️ Заморозка стріку",
        description="Захисти свій стрік від скидання на 1 день. Можна мати до 3 заморозок.",
        payload="streak_freeze_1",
        provider_token="",  # Stars payment
        currency="XTR",
        prices=[LabeledPrice("Заморозка стріку", 15)],  # 15 Stars
    )


async def cmd_subscribe(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Send Telegram Stars invoice for Premium subscription."""
    await update.message.reply_invoice(
        title="⭐ ThreeWords Premium — 30 днів",
        description=(
            "🔓 Персонажі Vex і Seraph\n"
            "⚡ Подвійний XP на всі уроки\n"
            "🏆 Іконка Premium у Leaderboard\n"
            "📊 Персональна AI-аналітика прогресу"
        ),
        payload="premium_30d",
        currency="XTR",            # Telegram Stars
        prices=[LabeledPrice("Premium 30 днів", PREMIUM_STARS)],
        photo_url="https://threewords-app.vercel.app/icon-192.png",
        photo_width=192,
        photo_height=192,
    )


async def cb_pre_checkout(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Approve all Stars payments."""
    await update.pre_checkout_query.answer(ok=True)


async def cb_successful_payment(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Activate premium or streak freeze after Stars payment."""
    payment = update.message.successful_payment
    tg_id = update.effective_user.id
    stars = payment.total_amount  # in Stars (XTR has no subunits)
    payload = payment.invoice_payload

    if payload.startswith("streak_freeze"):
        import aiosqlite
        db_path = getattr(database, "DB_PATH", None) or os.path.join(os.path.dirname(os.path.abspath(__file__)), "miniapp", "threewords.db")
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "UPDATE users SET streak_freeze = MIN(3, COALESCE(streak_freeze, 0) + 1) WHERE tg_id=?",
                (tg_id,)
            )
            await db.commit()
        await update.message.reply_text(
            "❄️ Заморозка стріку активована!\n\n"
            "Якщо завтра не встигнеш пройти урок — твій стрік збережеться.\n"
            "Команда /stats щоб побачити запаси заморозок."
        )
        return

    # Notify our local API to activate premium in DB
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{API_BASE}/api/premium/activate",
                json={"tg_id": tg_id, "stars": stars, "secret": PREMIUM_SECRET},
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                result = await resp.json()
                expires = result.get("premium_expires", "?")
    except Exception:
        expires = "~30 днів"

    await update.message.reply_text(
        f"🎉 *Дякуємо! Premium активовано!*\n\n"
        f"⭐ Сплачено: {stars} Stars\n"
        f"📅 Діє до: {expires}\n\n"
        f"🔓 Vex та Seraph тепер доступні у міні-апп!\n"
        f"⚡ Подвійний XP на всі уроки!\n\n"
        f"Відкрий гру: /app",
        parse_mode=ParseMode.MARKDOWN,
    )


def _register_jobs(app: Application) -> None:
    """Register APScheduler jobs via python-telegram-bot's JobQueue."""
    jq = app.job_queue
    if jq is None:
        log.warning("JobQueue is not available. Scheduled posts will not run.")
        return

    # 09:00 Kyiv — word of the day
    jq.run_daily(
        job_morning_word,
        time=datetime.now(UKRAINE_TZ).replace(hour=9, minute=0, second=0, microsecond=0).timetz(),
        name="morning_word",
    )
    # 12:00 Kyiv — quiz poll
    jq.run_daily(
        job_midday_quiz,
        time=datetime.now(UKRAINE_TZ).replace(hour=12, minute=0, second=0, microsecond=0).timetz(),
        name="midday_quiz",
    )
    # 20:00 Kyiv — evening motivation
    jq.run_daily(
        job_evening_motivation,
        time=datetime.now(UKRAINE_TZ).replace(hour=20, minute=0, second=0, microsecond=0).timetz(),
        name="evening_motivation",
    )
    log.info("Scheduled jobs registered: 09:00, 12:00, 20:00 Kyiv time.")


async def main() -> None:
    app: Application = (
        ApplicationBuilder()
        .token(LEARNING_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    _register_handlers(app)
    _register_jobs(app)

    await app.initialize()
    await app.start()
    await app.updater.start_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )
    log.info("ThreeWordsDaily learning bot online.")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
