"""
bot_main.py — @ThreeWordsDailyBot (повна версія з DB + Mini App)
Запуск: python3 bot_main.py

Команди:
  /start    — вітання / онбординг нового або меню поверненого
  /menu     — головне меню
  /today    — урок дня (3 слова + idiom + mini quiz)
  /quiz     — тест по поточному уроку
  /review   — повторення вивчених слів
  /top      — лідерборд (топ 5)
  /progress — статистика
  /help     — допомога
"""

import asyncio
import json
import os
import random
import sys
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from openai import AsyncOpenAI
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    BotCommand, WebAppInfo,
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters,
)

load_dotenv()

BOT_TOKEN     = os.getenv("TELEGRAM_BOT_TOKEN", "8681431935:AAGGFw6AnGbs23_Wb2wRqZ4GM0WutK93wM0")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID      = int(os.getenv("ADMIN_CHAT_ID", "6923740900"))
GROUP_ID      = int(os.getenv("TELEGRAM_CHAT_ID", "-1002680027938"))
MINI_APP_URL  = "https://threewords-app.vercel.app"

openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ======= DATABASE INTEGRATION =======

# Import database from parent dir (same dir as this file)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import database
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

# In-memory fallback for bot (used if DB not ready)
_users_mem: dict[int, dict] = {}


def _get_user_mem(user_id: int, first_name: str = "") -> dict:
    if user_id not in _users_mem:
        _users_mem[user_id] = {
            "first_name": first_name or "Друже",
            "level": None,
            "topic": None,
            "streak": 0,
            "last_lesson_date": None,
            "words_learned": [],
            "total_lessons": 0,
            "total_quizzes": 0,
            "correct_answers": 0,
            "xp": 0,
            "current_lesson": None,
            "quiz_words": [],
            "quiz_index": 0,
            "referrer": None,
            "referrals": 0,
            "registered_at": str(date.today()),
        }
    if first_name:
        _users_mem[user_id]["first_name"] = first_name
    return _users_mem[user_id]


async def _get_user(user_id: int, first_name: str = "", username: str = "") -> dict:
    if DB_AVAILABLE:
        try:
            return await database.get_or_create_user(user_id, first_name, username)
        except Exception:
            pass
    return _get_user_mem(user_id, first_name)


async def _update_user(user_id: int, **fields):
    if DB_AVAILABLE:
        try:
            await database.update_user(user_id, **fields)
        except Exception:
            pass
    # Also update in-memory
    mem = _get_user_mem(user_id)
    mem.update(fields)


def get_rank(xp: int) -> tuple[str, int]:
    if xp >= 1000: return "👑 Майстер", 9999
    if xp >= 500:  return "💎 Експерт", 1000
    if xp >= 200:  return "🔥 Практик", 500
    if xp >= 50:   return "⚡ Учень", 200
    return "🌱 Новачок", 50


def update_streak_mem(user_id: int):
    u = _get_user_mem(user_id)
    today = str(date.today())
    if u["last_lesson_date"] == today:
        return
    yesterday = str(date.today() - timedelta(days=1))
    if u["last_lesson_date"] == yesterday:
        u["streak"] += 1
    else:
        u["streak"] = 1
    u["last_lesson_date"] = today
    u["xp"] += 10


# ======= MINI APP KEYBOARD HELPER =======

def mini_app_btn(label: str = "🎮 Відкрити Mini App") -> InlineKeyboardButton:
    return InlineKeyboardButton(label, web_app=WebAppInfo(url=MINI_APP_URL))


# ======= MAIN MENU KEYBOARD =======

def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Primary CTA: Mini App. Secondary: quick info commands."""
    return InlineKeyboardMarkup([
        [mini_app_btn("🎮 Відкрити Mini App — вчись тут!")],
        [
            InlineKeyboardButton("📊 Прогрес",  callback_data="show_progress"),
            InlineKeyboardButton("🏆 Рейтинг",  callback_data="show_top"),
        ],
    ])


# ======= AI ГЕНЕРАЦІЯ =======

async def generate_lesson(level: str, topic: str) -> dict:
    topic_names = {
        "work": "Робота та бізнес", "travel": "Подорожі",
        "everyday": "Повсякденне", "emotions": "Емоції",
        "technology": "Технології", "mixed": "різні теми",
    }
    topic_ua = topic_names.get(topic, topic)

    resp = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "Ти вчитель англійської для українців. "
                    "Відповідай ТІЛЬКИ валідним JSON без markdown та ``` блоків."
                ),
            },
            {
                "role": "user",
                "content": f"""Створи урок англійської.
Рівень: {level}
Тема: {topic_ua}

Поверни ТІЛЬКИ JSON (без markdown):
{{
  "words": [
    {{
      "word": "ambitious",
      "transcription": "/æmˈbɪʃəs/",
      "translation": "амбітний",
      "example": "She is very ambitious about her career.",
      "example_ua": "Вона дуже амбітна щодо своєї кар'єри."
    }}
  ],
  "idiom": {{
    "text": "go the extra mile",
    "translation": "докласти додаткових зусиль",
    "example": "He always goes the extra mile at work.",
    "example_ua": "Він завжди докладає додаткових зусиль на роботі."
  }},
  "mini_story": "Short 2-3 sentence story using all 3 words in English.",
  "mini_story_ua": "Переклад story українською."
}}

Рівно 3 слова, тема: {topic_ua}, рівень {level}.""",
            },
        ],
        max_tokens=1200,
        temperature=0.7,
    )
    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


async def generate_quiz_questions(words: list) -> list:
    wrong_pool = [
        "втомлений", "сміливий", "щасливий", "серйозний",
        "спокійний", "розчарований", "цікавий", "складний",
        "дружній", "активний", "ефективний", "важкий",
        "веселий", "сумний", "розумний", "тихий",
    ]
    questions = []
    for w in words:
        wrongs = random.sample([x for x in wrong_pool if x != w["translation"]], 3)
        answers = [w["translation"]] + wrongs
        random.shuffle(answers)
        correct_idx = answers.index(w["translation"])
        questions.append({
            "question": f'❓ Що означає слово "{w["word"]}" {w["transcription"]}?',
            "answers": answers,
            "correct": correct_idx,
            "word": w["word"],
        })
    return questions


async def ai_explain(word: str, context: str = "") -> str:
    resp = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": (
                f"Поясни слово '{word}' для учня англійської.\n"
                f"Дай 2 додаткові приклади речень.\n"
                f"Відповідай українською, коротко і зрозуміло.\n"
                f"{f'Контекст: {context}' if context else ''}"
            ),
        }],
        max_tokens=250,
        temperature=0.6,
    )
    return resp.choices[0].message.content.strip()


async def generate_review_quiz(words: list) -> list:
    sample = random.sample(words, min(5, len(words)))
    wrong_pool = [
        "time", "place", "mind", "heart", "power",
        "dream", "light", "money", "skill", "voice",
        "hope", "fire", "water", "spirit", "force",
    ]
    questions = []
    for word in sample:
        bad_words = [w for w in wrong_pool if w != word]
        wrongs = random.sample(bad_words, 3)
        answers = [word] + wrongs
        random.shuffle(answers)
        questions.append({
            "question": "❓ Яке слово ти вивчав/ла?",
            "word_ua": word,
            "answers": answers,
            "correct": answers.index(word),
            "word": word,
        })
    return questions


# ======= /start =======

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name or "Друже"
    username = update.effective_user.username or ""

    u = await _get_user(user_id, first_name, username)

    # Referral handling
    args = ctx.args
    if args and args[0].startswith("ref_"):
        ref_id_str = args[0].replace("ref_", "")
        try:
            ref_id = int(ref_id_str)
            if ref_id != user_id:
                referrer_id = u.get("referrer_id") or u.get("referrer")
                if referrer_id is None:
                    await _update_user(user_id, referrer_id=ref_id)
                    # Award referrer
                    ref_u = await _get_user(ref_id)
                    if ref_u:
                        new_xp = ref_u.get("xp", 0) + 25
                        new_refs = ref_u.get("referrals_count", 0) + 1
                        await _update_user(ref_id, xp=new_xp, referrals_count=new_refs)
                        if DB_AVAILABLE:
                            try:
                                await database.add_progress_event(ref_id, "referral", 25)
                            except Exception:
                                pass
                    # Bonus for new user
                    await _update_user(user_id, xp=(u.get("xp", 0) + 10))
                    try:
                        await ctx.bot.send_message(
                            ref_id,
                            f"🎉 Твій друг *{first_name}* приєднався по твоєму посиланню!\n"
                            f"*+25 XP* нараховано! Продовжуй запрошувати 🚀",
                            parse_mode="Markdown",
                        )
                    except Exception:
                        pass
        except ValueError:
            pass

    level = u.get("level")
    xp = u.get("xp", 0)
    streak = u.get("streak", 0)
    rank, _ = get_rank(xp)

    if level:
        # Returning user — push to Mini App
        words = u.get("words_learned") or []
        if isinstance(words, str):
            import json as _json
            try: words = _json.loads(words)
            except: words = []
        companion_stage = min(5, len(words) // 10)
        stage_names = ["🥚 Яйце", "🐣 Малюк", "🌟 Дух слів", "🦋 Мудрець", "🔮 Легенда", "⚡ Хаос"]
        companion = stage_names[companion_stage]
        text = (
            f"👋 З поверненням, *{first_name}*!\n\n"
            f"{rank} · ⭐ {xp} XP · 🔥 {streak} streak\n\n"
            f"Твій компаньйон: *{companion}*\n"
            f"📖 Слів вивчено: *{len(words)}*\n\n"
            f"Всі уроки, ігри та еволюція — в Mini App 👇"
        )
        await update.message.reply_text(text, reply_markup=main_menu_keyboard(), parse_mode="Markdown")
    else:
        # New user — onboarding: level pick
        keyboard = [
            [InlineKeyboardButton("🟢 A1 — Початківець",     callback_data="level_A1")],
            [InlineKeyboardButton("🔵 A2 — Базовий",         callback_data="level_A2")],
            [InlineKeyboardButton("🟡 B1 — Середній",        callback_data="level_B1")],
            [InlineKeyboardButton("🟠 B2 — Вище середнього", callback_data="level_B2")],
        ]
        text = (
            f"👋 Привіт, *{first_name}*!\n\n"
            f"Я — *ThreeWordsDaily* — твій AI‑вчитель англійської.\n\n"
            f"🥚 Тебе чекає *Лексик* — живий компаньйон!\n"
            f"Обери архетип у додатку:\n"
            f"✨ *Spirit* · 🦊 *Beast* · 🤖 *Buddy*\n\n"
            f"Він росте разом з тобою:\n"
            f"• 3 слова на день + idiom + story\n"
            f"• Ігри: Fast Tap, Match Pairs, Memory\n"
            f"• Еволюція: 🥚→🌱→🌟→🦋→🔮→⚡\n"
            f"• 🏆 Лідер місяця отримує *Telegram Premium*\n\n"
            f"Спочатку — твій рівень англійської:"
        )
        await update.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )


async def cmd_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name or "Друже"
    u = await _get_user(user_id, first_name)
    xp = u.get("xp", 0)
    streak = u.get("streak", 0)
    rank, _ = get_rank(xp)

    await update.message.reply_text(
        f"🎮 *ThreeWordsDaily*\n\n"
        f"{rank} · ⭐ {xp} XP · 🔥 {streak} streak\n\n"
        f"Відкрий Mini App — там Лексик, ігри та прогрес 👇",
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown",
    )


async def cb_level(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    level = query.data.replace("level_", "")
    await _update_user(user_id, level=level)

    keyboard = [
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
    ]
    await query.edit_message_text(
        f"✅ Рівень: **{level}**\n\nТепер обери тему:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def cb_topic(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    topic = query.data.replace("topic_", "")
    topic_names = {
        "work": "Робота та бізнес", "travel": "Подорожі",
        "everyday": "Повсякденне",  "emotions": "Емоції",
        "technology": "Технології", "mixed": "Мікс",
    }
    await _update_user(user_id, topic=topic)

    keyboard = [[mini_app_btn("🎮 Відкрити Mini App — починаємо!")]]
    await query.edit_message_text(
        f"✅ Тема: **{topic_names.get(topic, topic)}**\n\n"
        f"Чудовий вибір! 💪\n"
        f"Лексик вже чекає в Mini App — вилупись і почни вчитись 🥚",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


# ======= УРОК =======

async def send_lesson(chat_id: int, user_id: int, ctx: ContextTypes.DEFAULT_TYPE, edit_message=None):
    u = await _get_user(user_id)
    level = u.get("level") or "A2"
    topic = u.get("topic") or "everyday"

    wait_text = "⏳ AI генерує твій урок..."
    if edit_message:
        await edit_message.edit_text(wait_text)
    else:
        await ctx.bot.send_message(chat_id, wait_text)

    try:
        lesson = await generate_lesson(level, topic)
    except Exception as e:
        err = f"❌ Не вдалось згенерувати урок: {e}\n\nСпробуй /today ще раз"
        if edit_message:
            await edit_message.edit_text(err)
        else:
            await ctx.bot.send_message(chat_id, err)
        return

    # Save lesson in memory
    _get_user_mem(user_id)["current_lesson"] = lesson
    update_streak_mem(user_id)

    # Update in DB
    today = str(date.today())
    yesterday = str(date.today() - timedelta(days=1))
    old_last = u.get("last_lesson_date")
    new_streak = u.get("streak", 0)
    if old_last != today:
        if old_last == yesterday:
            new_streak += 1
        else:
            new_streak = 1
        await _update_user(
            user_id,
            last_lesson_date=today,
            streak=new_streak,
            total_lessons=(u.get("total_lessons", 0) + 1),
        )

    # Format lesson text
    words_text = ""
    for i, w in enumerate(lesson["words"], 1):
        words_text += (
            f"{i}. **{w['word']}** `{w['transcription']}`\n"
            f"   🇺🇦 _{w['translation']}_\n"
            f"   💬 {w['example']}\n"
            f"   _{w['example_ua']}_\n\n"
        )

    idiom = lesson["idiom"]
    rank, _ = get_rank(u.get("xp", 0))
    text = (
        f"📚 **Урок дня** | {level} | 🔥 Streak: {new_streak}\n"
        f"━━━━━━━━━━━━━━━━━\n\n"
        f"**Слова:**\n\n{words_text}"
        f"💬 **Idiom дня:**\n"
        f"_{idiom['text']}_ — {idiom['translation']}\n"
        f"💡 _{idiom['example']}_\n"
        f"_{idiom['example_ua']}_\n\n"
        f"📖 **Mini-story:**\n"
        f"_{lesson['mini_story']}_\n"
        f"_{lesson['mini_story_ua']}_"
    )

    keyboard = [
        [
            InlineKeyboardButton("🧠 Тест (3 питання)", callback_data="quiz_now"),
            InlineKeyboardButton("💡 Пояснення AI",     callback_data="explain_word"),
        ],
        [
            InlineKeyboardButton("📝 Ще приклади",      callback_data="more_examples"),
            InlineKeyboardButton("✅ Вивчив! +20 XP",   callback_data="mark_learned"),
        ],
        [
            InlineKeyboardButton("⏭ Наступний урок",    callback_data="next_lesson"),
            mini_app_btn("🎮 Mini App"),
        ],
    ]

    try:
        if edit_message:
            await edit_message.edit_text(
                text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
            )
        else:
            await ctx.bot.send_message(
                chat_id, text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
            )
    except Exception:
        simple = f"📚 Урок дня | {level}\n━━━━━━━━━━━━━━━━━\n\n"
        for i, w in enumerate(lesson["words"], 1):
            simple += f"{i}. {w['word']} {w['transcription']}\n🇺🇦 {w['translation']}\n💬 {w['example']}\n\n"
        simple += f"💬 Idiom: {idiom['text']} — {idiom['translation']}\n\n"
        simple += f"📖 Story: {lesson['mini_story']}"
        if edit_message:
            await edit_message.edit_text(simple, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await ctx.bot.send_message(chat_id, simple, reply_markup=InlineKeyboardMarkup(keyboard))


async def cmd_today(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = await _get_user(update.effective_user.id, update.effective_user.first_name or "")
    if not u.get("level"):
        await update.message.reply_text(
            "Спочатку налаштуй профіль:\nНапиши /start і обери рівень та тему."
        )
        return
    await send_lesson(update.effective_chat.id, update.effective_user.id, ctx)


async def cb_start_lesson(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await send_lesson(query.message.chat_id, query.from_user.id, ctx, edit_message=query.message)


async def cb_next_lesson(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("⏳ Генерую...")
    await send_lesson(query.message.chat_id, query.from_user.id, ctx, edit_message=query.message)


# ======= QUIZ =======

async def start_quiz_session(chat_id: int, user_id: int, ctx: ContextTypes.DEFAULT_TYPE, from_msg=None):
    u = _get_user_mem(user_id)
    lesson = u.get("current_lesson")
    if not lesson:
        text = "Спочатку пройди урок! /today"
        if from_msg:
            await from_msg.edit_text(text)
        else:
            await ctx.bot.send_message(chat_id, text)
        return

    questions = await generate_quiz_questions(lesson["words"])
    u["quiz_words"] = questions
    u["quiz_index"] = 0
    u["quiz_score"] = 0
    await send_quiz_question(chat_id, user_id, ctx, from_msg)


async def send_quiz_question(chat_id: int, user_id: int, ctx: ContextTypes.DEFAULT_TYPE, from_msg=None):
    u = _get_user_mem(user_id)
    questions = u.get("quiz_words", [])
    idx = u.get("quiz_index", 0)

    if idx >= len(questions):
        score = u.get("quiz_score", 0)
        total = len(questions)
        xp_earned = score * 15
        mem_xp = u.get("xp", 0) + xp_earned
        u["xp"] = mem_xp
        u["total_quizzes"] = u.get("total_quizzes", 0) + 1
        u["correct_answers"] = u.get("correct_answers", 0) + score

        await _update_user(user_id,
            xp=mem_xp,
            total_quizzes=u["total_quizzes"],
            correct_answers=u["correct_answers"],
        )

        stars = "⭐" * score + "☆" * (total - score)
        text = (
            f"🏁 **Тест завершено!**\n\n"
            f"{stars}\n"
            f"Правильно: **{score}/{total}**\n"
            f"Зароблено: **+{xp_earned} XP** 🎉\n\n"
            f"⭐ Всього XP: **{mem_xp}**"
        )
        keyboard = [
            [
                InlineKeyboardButton("📚 Новий урок",   callback_data="start_lesson"),
                InlineKeyboardButton("📊 Прогрес",      callback_data="show_progress"),
            ],
            [
                InlineKeyboardButton("🔄 Ще раз тест",  callback_data="quiz_now"),
                mini_app_btn("🎮 Mini App"),
            ],
        ]
        if from_msg:
            await from_msg.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        else:
            await ctx.bot.send_message(chat_id, text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    q = questions[idx]
    text = f"🧠 **Питання {idx + 1}/{len(questions)}**\n\n{q['question']}"
    answers_kb = [
        [InlineKeyboardButton(ans, callback_data=f"qa_{i}")]
        for i, ans in enumerate(q["answers"])
    ]
    if from_msg:
        await from_msg.edit_text(text, reply_markup=InlineKeyboardMarkup(answers_kb), parse_mode="Markdown")
    else:
        await ctx.bot.send_message(chat_id, text, reply_markup=InlineKeyboardMarkup(answers_kb), parse_mode="Markdown")


async def cmd_quiz(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await start_quiz_session(update.effective_chat.id, update.effective_user.id, ctx)


async def cb_quiz_now(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await start_quiz_session(query.message.chat_id, query.from_user.id, ctx, from_msg=query.message)


async def cb_quiz_answer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    answer_idx = int(query.data.replace("qa_", ""))
    u = _get_user_mem(user_id)
    questions = u.get("quiz_words", [])
    idx = u.get("quiz_index", 0)

    if idx >= len(questions):
        await query.answer("Тест вже завершено")
        return

    q = questions[idx]
    correct = q["correct"]

    if answer_idx == correct:
        u["quiz_score"] = u.get("quiz_score", 0) + 1
        await query.answer("✅ Правильно!")
        result_text = f"✅ **Правильно!**\n\n_{q['answers'][correct]}_ — вірна відповідь 🎯"
    else:
        await query.answer("❌ Не вірно")
        result_text = (
            f"❌ **Не вірно**\n\n"
            f"Правильна відповідь: _{q['answers'][correct]}_\n"
            f"Не здавайся! 💪"
        )

    u["quiz_index"] = idx + 1
    next_kb = [[InlineKeyboardButton("➡️ Далі", callback_data="quiz_next")]]
    await query.message.edit_text(result_text, reply_markup=InlineKeyboardMarkup(next_kb), parse_mode="Markdown")


async def cb_quiz_next(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await send_quiz_question(query.message.chat_id, query.from_user.id, ctx, from_msg=query.message)


# ======= REVIEW =======

async def cmd_review(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u = await _get_user(user_id)
    words = u.get("words_learned") or []
    if isinstance(words, str):
        words = json.loads(words)

    if len(words) < 3:
        await update.message.reply_text(
            f"У тебе поки що {len(words)} вивчених слів.\n"
            f"Потрібно мінімум 3 для повторення!\n\n"
            f"Пройди кілька уроків /today і повертайся 💪"
        )
        return

    questions = await generate_review_quiz(words)
    mem_u = _get_user_mem(user_id)
    mem_u["quiz_words"] = questions
    mem_u["quiz_index"] = 0
    mem_u["quiz_score"] = 0
    mem_u["quiz_mode"] = "review"

    await ctx.bot.send_message(
        update.effective_chat.id,
        f"🔄 **Повторення слів**\n\n"
        f"У тебе {len(words)} вивчених слів.\n"
        f"Тест на {len(questions)} питань — починаємо! 🚀",
        parse_mode="Markdown",
    )
    await send_quiz_question(update.effective_chat.id, user_id, ctx)


async def cb_do_review(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    u = await _get_user(user_id)
    words = u.get("words_learned") or []
    if isinstance(words, str):
        words = json.loads(words)

    if len(words) < 3:
        await query.edit_message_text(
            f"У тебе поки {len(words)} вивчених слів. Потрібно мінімум 3.\n\n"
            f"Пройди урок /today 📚",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📚 Урок дня", callback_data="start_lesson")
            ]])
        )
        return

    questions = await generate_review_quiz(words)
    mem_u = _get_user_mem(user_id)
    mem_u["quiz_words"] = questions
    mem_u["quiz_index"] = 0
    mem_u["quiz_score"] = 0
    mem_u["quiz_mode"] = "review"
    await send_quiz_question(query.message.chat_id, user_id, ctx, from_msg=query.message)


# ======= TOP =======

async def cmd_top(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    caller_id = update.effective_user.id
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    text = "🏆 **Топ гравців ThreeWordsDaily**\n━━━━━━━━━━━━━━━━━\n\n"
    caller_rank = None

    if DB_AVAILABLE:
        try:
            leaders = await database.get_leaderboard(limit=5)
            for i, u in enumerate(leaders):
                name = u.get("first_name", "Гравець")
                xp = u.get("xp", 0)
                streak = u.get("streak", 0)
                me = " ← ти" if u.get("tg_id") == caller_id else ""
                rank_label, _ = get_rank(xp)
                text += f"{medals[i] if i < 5 else f'#{i+1}'} **{name}**{me}\n{rank_label} | ⭐ {xp} | 🔥 {streak}\n\n"
                if u.get("tg_id") == caller_id:
                    caller_rank = i + 1
        except Exception:
            leaders = []
    else:
        sorted_u = sorted(_users_mem.items(), key=lambda x: x[1].get("xp", 0), reverse=True)
        top5 = sorted_u[:5]
        for i, (uid, u) in enumerate(top5):
            name = u.get("first_name", f"User{uid}")
            xp = u.get("xp", 0)
            streak = u.get("streak", 0)
            me = " ← ти" if uid == caller_id else ""
            rank_label, _ = get_rank(xp)
            text += f"{medals[i]} **{name}**{me}\n{rank_label} | ⭐ {xp} | 🔥 {streak}\n\n"
            if uid == caller_id:
                caller_rank = i + 1

    if caller_rank is None:
        my = await _get_user(caller_id)
        text += f"\n👤 Твоя позиція: за лідерами\n⭐ {my.get('xp', 0)} XP | 🔥 {my.get('streak', 0)} streak"

    keyboard = [
        [
            InlineKeyboardButton("📚 Урок дня", callback_data="start_lesson"),
            InlineKeyboardButton("📊 Мій прогрес", callback_data="show_progress"),
        ],
        [mini_app_btn("🎮 Відкрити Mini App")],
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


# ======= CALLBACKS =======

async def cb_more_examples(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("⏳ AI генерує...")
    u = _get_user_mem(query.from_user.id)
    lesson = u.get("current_lesson")
    if not lesson:
        await query.answer("Спочатку пройди урок!")
        return
    keyboard = [[InlineKeyboardButton(f"💡 {w['word']}", callback_data=f"explain_{w['word']}")] for w in lesson["words"]]
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="start_lesson")])
    await query.message.edit_text("Для якого слова пояснення?", reply_markup=InlineKeyboardMarkup(keyboard))


async def cb_explain_specific(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    word = query.data.replace("explain_", "")
    await query.answer("⏳ AI пояснює...")
    explanation = await ai_explain(word)
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="start_lesson")]]
    await query.message.edit_text(
        f"💡 **{word}:**\n\n{explanation}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def cb_explain_word(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("⏳ AI пояснює...")
    u = _get_user_mem(query.from_user.id)
    lesson = u.get("current_lesson")
    if not lesson:
        await query.answer("Спочатку пройди урок!")
        return
    words_list = ", ".join(w["word"] for w in lesson["words"])
    explanation = await ai_explain(words_list, "поясни кожне слово і різницю між ними")
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="start_lesson")]]
    await query.message.edit_text(
        f"🤖 **AI пояснює:**\n\n{explanation}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def cb_mark_learned(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    mem_u = _get_user_mem(user_id)
    lesson = mem_u.get("current_lesson")
    new_words = []
    if lesson:
        for w in lesson["words"]:
            if w["word"] not in mem_u["words_learned"]:
                mem_u["words_learned"].append(w["word"])
                new_words.append(w["word"])
        mem_u["xp"] = mem_u.get("xp", 0) + 20

    await _update_user(user_id,
        xp=mem_u["xp"],
        words_learned=json.dumps(mem_u["words_learned"]),
    )

    rank, _ = get_rank(mem_u["xp"])
    await query.answer("✅ +20 XP! Слова збережено!")
    keyboard = [
        [
            InlineKeyboardButton("⏭ Новий урок",     callback_data="next_lesson"),
            InlineKeyboardButton("📊 Прогрес",        callback_data="show_progress"),
        ],
        [
            InlineKeyboardButton("🧠 Тест",           callback_data="quiz_now"),
            mini_app_btn("🎮 Mini App"),
        ],
    ]
    await query.message.edit_text(
        f"✅ **Чудова робота!** +20 XP 🎉\n\n"
        f"{rank}\n\n"
        f"📚 Додано слів: **+{len(new_words)}**\n"
        f"📖 Всього у словнику: **{len(mem_u['words_learned'])}**\n"
        f"⭐ XP: **{mem_u['xp']}**\n"
        f"🔥 Streak: **{mem_u.get('streak', 0)} днів**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


# ======= ПРОГРЕС =======

async def build_progress_text(user_id: int, first_name: str) -> tuple[str, InlineKeyboardMarkup]:
    u = await _get_user(user_id)
    mem_u = _get_user_mem(user_id)

    xp = u.get("xp", 0)
    streak = u.get("streak", 0)
    words = u.get("words_learned") or []
    if isinstance(words, str):
        words = json.loads(words)

    total_lessons = u.get("total_lessons", 0)
    total_quizzes = u.get("total_quizzes", 0)
    correct_answers = u.get("correct_answers", 0)
    refs = u.get("referrals_count", 0) or u.get("referrals", 0)
    ref_xp = refs * 25

    rank, next_xp = get_rank(xp)
    accuracy = 0
    if total_quizzes > 0:
        total_q = total_quizzes * 3
        accuracy = int((correct_answers / total_q) * 100) if total_q > 0 else 0

    position = "?"
    if DB_AVAILABLE:
        try:
            stats = await database.get_user_stats(user_id)
            position = stats.get("rank", "?")
        except Exception:
            pass

    companion_stage = min(5, len(words) // 10)
    stage_names = ["🥚 Яйце", "🐣 Малюк", "🌟 Дух слів", "🦋 Мудрець", "🔮 Легенда", "⚡ Хаос"]
    companion = stage_names[companion_stage]

    text = (
        f"📊 *{first_name}*\n"
        f"━━━━━━━━━━━━━━━━━\n\n"
        f"{rank} · до наступного: *{max(0, next_xp - xp)} XP*\n\n"
        f"🐾 Лексик: *{companion}*\n"
        f"🔥 Streak: *{streak} днів*\n"
        f"💾 Слів: *{len(words)}*\n"
        f"📚 Уроків: *{total_lessons}*\n"
        f"🧠 Тестів: *{total_quizzes}* (точність {accuracy}%)\n"
        f"⭐ XP: *{xp}* · 🏆 #{position}\n\n"
        f"👥 Рефералів: *{refs}* (+{ref_xp} XP)"
    )
    keyboard = InlineKeyboardMarkup([
        [mini_app_btn("🎮 Відкрити Mini App")],
        [InlineKeyboardButton("🏆 Рейтинг", callback_data="show_top")],
    ])
    return text, keyboard


async def cmd_progress(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text, kb = await build_progress_text(update.effective_user.id, update.effective_user.first_name)
    await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def cb_show_progress(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text, kb = await build_progress_text(query.from_user.id, query.from_user.first_name)
    await query.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


async def cb_show_top(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    text = "🏆 **Топ гравців**\n━━━━━━━━━━━━━━━━━\n\n"

    if DB_AVAILABLE:
        try:
            leaders = await database.get_leaderboard(limit=5)
            for i, u in enumerate(leaders):
                name = u.get("first_name", "Гравець")
                xp = u.get("xp", 0)
                streak = u.get("streak", 0)
                me = " ← ти" if u.get("tg_id") == query.from_user.id else ""
                text += f"{medals[i] if i < 5 else f'#{i+1}'} **{name}**{me} — ⭐{xp} | 🔥{streak}д\n"
        except Exception:
            text += "Помилка завантаження"
    else:
        sorted_u = sorted(_users_mem.items(), key=lambda x: x[1].get("xp", 0), reverse=True)[:5]
        for i, (uid, u) in enumerate(sorted_u):
            name = u.get("first_name", f"User{uid}")
            me = " ← ти" if uid == query.from_user.id else ""
            text += f"{medals[i]} **{name}**{me} — ⭐{u.get('xp',0)} | 🔥{u.get('streak',0)}д\n"

    keyboard = [
        [InlineKeyboardButton("◀️ Назад", callback_data="show_progress")],
        [mini_app_btn("🎮 Mini App — повний рейтинг")],
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


# ======= HELP =======

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u = await _get_user(user_id)
    try:
        bot_username = (await ctx.bot.get_me()).username
    except Exception:
        bot_username = "ThreeWordsDailyBot"
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"

    await update.message.reply_text(
        f"📖 *ThreeWordsDaily*\n\n"
        f"Вся навчалка — в Mini App:\n"
        f"• 📚 Урок дня (3 слова + idiom)\n"
        f"• 🎮 Ігри: Fast Tap · Match Pairs · Memory\n"
        f"• 🐾 Лексик: ✨Spirit / 🦊Beast / 🤖Buddy\n"
        f"• 🥚→⚡ Еволюція компаньйона\n"
        f"• 🏆 Рейтинг · 🎩 Скіни · Нагороди\n\n"
        f"Команди:\n"
        f"/progress — мій прогрес\n"
        f"/top — рейтинг\n"
        f"/menu — меню\n\n"
        f"💬 Напиши будь-яке слово — поясню!\n\n"
        f"🔗 *Реф. посилання:*\n`{ref_link}`\n"
        f"За друга → +25 XP тобі, +10 XP другу!",
        reply_markup=InlineKeyboardMarkup([[mini_app_btn("🎮 Відкрити Mini App")]]),
        parse_mode="Markdown",
    )


# ======= TEXT HANDLER =======

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    msg = update.message
    text = msg.text.strip()
    user_id = update.effective_user.id
    is_group = msg.chat.type in ("group", "supergroup")

    if is_group:
        try:
            bot_username = (await ctx.bot.get_me()).username
        except Exception:
            return
        is_mention = f"@{bot_username}" in text
        is_reply = msg.reply_to_message and msg.reply_to_message.from_user.id == ctx.bot.id
        if not is_mention and not is_reply:
            return
        text = text.replace(f"@{bot_username}", "").strip()

    if not text or len(text) > 150:
        return

    if len(text.split()) <= 4:
        await msg.reply_text("⏳ AI пояснює...")
        explanation = await ai_explain(text)
        keyboard = [[
            InlineKeyboardButton("📚 Урок дня", callback_data="start_lesson"),
            InlineKeyboardButton("🧠 Тест",     callback_data="quiz_now"),
        ]]
        await msg.reply_text(
            f"💡 **{text}:**\n\n{explanation}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
    else:
        await msg.reply_text("⏳ Перекладаю...")
        resp = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": (
                f"Перекладаю для учня англійської:\n'{text}'\n\n"
                f"Дай переклад українською і 1-2 корисних нотатки про граматику/вживання. Коротко."
            )}],
            max_tokens=200,
        )
        translation = resp.choices[0].message.content.strip()
        await msg.reply_text(f"🔤 **Переклад:**\n\n{translation}", parse_mode="Markdown")


# ======= NEW MEMBERS =======

async def handle_new_member(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.new_chat_members:
        return
    for member in update.message.new_chat_members:
        if member.is_bot:
            continue
        name = member.first_name or "Друже"
        await _get_user(member.id, name)
        await update.message.reply_text(
            f"👋 *{name}*, ласкаво просимо!\n\n"
            f"🥚 Тебе чекає *Лексик* — живий компаньйон!\n"
            f"Обери архетип: ✨ Spirit · 🦊 Beast · 🤖 Buddy\n\n"
            f"• 3 слова на день + idiom + story\n"
            f"• Ігри: Fast Tap · Match Pairs · Memory\n"
            f"• Еволюція: 🥚→🌱→🌟→🦋→🔮→⚡\n"
            f"• 🏆 Лідер місяця = *Telegram Premium*\n\n"
            f"Натисни /start 🚀",
            parse_mode="Markdown",
        )


# ======= SETUP =======

async def setup_commands(application: Application):
    await application.bot.set_my_commands([
        BotCommand("start",    "Почати / вибір рівня"),
        BotCommand("menu",     "Головне меню"),
        BotCommand("today",    "Урок дня (3 слова)"),
        BotCommand("quiz",     "Тест по поточному уроку"),
        BotCommand("review",   "Повторення вивчених слів"),
        BotCommand("top",      "Лідерборд 🏆"),
        BotCommand("progress", "Мій прогрес"),
        BotCommand("help",     "Допомога + реф. посилання"),
    ])


async def post_init(application: Application):
    await setup_commands(application)
    if DB_AVAILABLE:
        try:
            await database.init_db()
            print("✅ Database initialized")
        except Exception as e:
            print(f"⚠️  DB init failed: {e}")


def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # Commands
    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("menu",     cmd_menu))
    app.add_handler(CommandHandler("today",    cmd_today))
    app.add_handler(CommandHandler("quiz",     cmd_quiz))
    app.add_handler(CommandHandler("review",   cmd_review))
    app.add_handler(CommandHandler("top",      cmd_top))
    app.add_handler(CommandHandler("progress", cmd_progress))
    app.add_handler(CommandHandler("help",     cmd_help))

    # Callback buttons
    app.add_handler(CallbackQueryHandler(cb_level,           pattern="^level_"))
    app.add_handler(CallbackQueryHandler(cb_topic,           pattern="^topic_"))
    app.add_handler(CallbackQueryHandler(cb_start_lesson,    pattern="^start_lesson$"))
    app.add_handler(CallbackQueryHandler(cb_next_lesson,     pattern="^next_lesson$"))
    app.add_handler(CallbackQueryHandler(cb_quiz_now,        pattern="^quiz_now$"))
    app.add_handler(CallbackQueryHandler(cb_quiz_answer,     pattern="^qa_"))
    app.add_handler(CallbackQueryHandler(cb_quiz_next,       pattern="^quiz_next$"))
    app.add_handler(CallbackQueryHandler(cb_more_examples,   pattern="^more_examples$"))
    app.add_handler(CallbackQueryHandler(cb_explain_specific,pattern="^explain_[a-zA-Z]"))
    app.add_handler(CallbackQueryHandler(cb_explain_word,    pattern="^explain_word$"))
    app.add_handler(CallbackQueryHandler(cb_mark_learned,    pattern="^mark_learned$"))
    app.add_handler(CallbackQueryHandler(cb_show_progress,   pattern="^show_progress$"))
    app.add_handler(CallbackQueryHandler(cb_show_top,        pattern="^show_top$"))
    app.add_handler(CallbackQueryHandler(cb_do_review,       pattern="^do_review$"))

    # Messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_member))

    print("🤖 ThreeWordsDaily бот запущено! Ctrl+C для зупинки.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
