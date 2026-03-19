"""
bot_main.py — повноцінний @YourBot_prod_bot
Запуск: python3 bot_main.py

Команди:
  /start   — вибір рівня + теми + перший урок
  /today   — урок дня (3 слова + idiom + mini quiz)
  /quiz    — тест по вивченим словам
  /review  — повторення
  /progress — статистика
  /help    — допомога
"""

import asyncio
import json
import os
import random
from datetime import datetime, date
from dotenv import load_dotenv
from openai import AsyncOpenAI
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    BotCommand
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8681431935:AAGGFw6AnGbs23_Wb2wRqZ4GM0WutK93wM0")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ======= IN-MEMORY USER DATA (замінити на Sheets/SQLite в продакшені) =======
users: dict[int, dict] = {}

def get_user(user_id: int) -> dict:
    if user_id not in users:
        users[user_id] = {
            "level": None,
            "topic": None,
            "streak": 0,
            "last_lesson_date": None,
            "words_learned": [],
            "total_lessons": 0,
            "xp": 0,
            "current_lesson": None,  # слова поточного уроку
        }
    return users[user_id]

def update_streak(user_id: int):
    u = get_user(user_id)
    today = str(date.today())
    if u["last_lesson_date"] == today:
        return  # вже був урок сьогодні
    yesterday = str(date.today().replace(day=date.today().day - 1))
    if u["last_lesson_date"] == yesterday:
        u["streak"] += 1
    elif u["last_lesson_date"] != today:
        u["streak"] = 1
    u["last_lesson_date"] = today
    u["xp"] += 10

# ======= AI ГЕНЕРАЦІЯ =======

async def generate_lesson(level: str, topic: str) -> dict:
    """Генерує урок: 3 слова + idiom + quiz питання."""
    resp = await openai.chat.completions.create(
        model="gpt-4",
        messages=[{
            "role": "system",
            "content": "Ти вчитель англійської для українців. Відповідай тільки валідним JSON."
        }, {
            "role": "user",
            "content": f"""Створи урок англійської.
Рівень: {level}
Тема: {topic}

Поверни JSON:
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
  "quiz": {{
    "question": "Що означає 'ambitious'?",
    "answers": ["амбітний", "втомлений", "щасливий", "серйозний"],
    "correct": 0
  }},
  "mini_story": "Short 2-3 sentence story using these words in English.",
  "mini_story_ua": "Переклад story українською."
}}

3 слова, всі на тему '{topic}', рівень {level}. Тільки JSON."""
        }],
        max_tokens=1000,
        temperature=0.7,
    )
    return json.loads(resp.choices[0].message.content.strip())

async def ai_explain(word: str, context: str = "") -> str:
    """AI пояснення слова з прикладами."""
    resp = await openai.chat.completions.create(
        model="gpt-4",
        messages=[{
            "role": "user",
            "content": f"""Поясни слово '{word}' для учня англійської.
Дай 2 додаткові приклади речень.
Відповідай українською, коротко.
{f'Контекст: {context}' if context else ''}"""
        }],
        max_tokens=200,
        temperature=0.6,
    )
    return resp.choices[0].message.content.strip()

# ======= /start =======

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name or "друже"
    u = get_user(user_id)

    keyboard = [
        [InlineKeyboardButton("🟢 A1 — Початківець", callback_data="level_A1")],
        [InlineKeyboardButton("🔵 A2 — Базовий", callback_data="level_A2")],
        [InlineKeyboardButton("🟡 B1 — Середній", callback_data="level_B1")],
        [InlineKeyboardButton("🟠 B2 — Вище середнього", callback_data="level_B2")],
    ]
    await update.message.reply_text(
        f"👋 Привіт, {first_name}!\n\n"
        f"Я буду твоїм AI-вчителем англійської 🤖\n\n"
        f"📚 Щодня:\n"
        f"• 3 нових слова\n"
        f"• Idiom дня\n"
        f"• Mini quiz\n"
        f"• AI пояснення на запит\n\n"
        f"Спочатку — обери свій рівень:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def cb_level(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    level = query.data.replace("level_", "")
    get_user(user_id)["level"] = level

    keyboard = [
        [InlineKeyboardButton("💼 Робота та бізнес", callback_data="topic_work"),
         InlineKeyboardButton("✈️ Подорожі", callback_data="topic_travel")],
        [InlineKeyboardButton("💬 Повсякденне", callback_data="topic_everyday"),
         InlineKeyboardButton("❤️ Емоції", callback_data="topic_emotions")],
        [InlineKeyboardButton("💻 Технології", callback_data="topic_technology"),
         InlineKeyboardButton("🎲 Мікс", callback_data="topic_mixed")],
    ]
    await query.edit_message_text(
        f"✅ Рівень: **{level}**\n\nТепер обери тему:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def cb_topic(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    topic = query.data.replace("topic_", "")
    topic_names = {
        "work": "Робота та бізнес", "travel": "Подорожі",
        "everyday": "Повсякденне", "emotions": "Емоції",
        "technology": "Технології", "mixed": "Мікс"
    }
    get_user(user_id)["topic"] = topic

    keyboard = [[InlineKeyboardButton("🚀 Починаємо перший урок!", callback_data="start_lesson")]]
    await query.edit_message_text(
        f"✅ Тема: **{topic_names.get(topic, topic)}**\n\n"
        f"Все готово! Починаємо 💪",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ======= УРОК =======

async def send_lesson(chat_id: int, user_id: int, ctx: ContextTypes.DEFAULT_TYPE, edit_message=None):
    u = get_user(user_id)
    level = u.get("level", "A2")
    topic = u.get("topic", "everyday")

    # Надсилаємо повідомлення "генерую..."
    if edit_message:
        await edit_message.edit_text("⏳ Генерую урок...")
    else:
        msg = await ctx.bot.send_message(chat_id, "⏳ Генерую урок...")

    try:
        lesson = await generate_lesson(level, topic)
    except Exception as e:
        await ctx.bot.send_message(chat_id, f"❌ Помилка генерації: {e}")
        return

    u["current_lesson"] = lesson
    update_streak(user_id)
    u["total_lessons"] += 1

    # Форматуємо слова
    words_text = ""
    for i, w in enumerate(lesson["words"], 1):
        words_text += (
            f"{i}. **{w['word']}** `{w['transcription']}`\n"
            f"   🇺🇦 {w['translation']}\n"
            f"   💬 _{w['example']}_\n"
            f"   _{w['example_ua']}_\n\n"
        )

    idiom = lesson["idiom"]
    text = (
        f"📚 **Урок дня** | {level} | {topic}\n"
        f"━━━━━━━━━━━━━━━━━\n\n"
        f"**Слова:**\n\n{words_text}"
        f"💬 **Idiom дня:**\n"
        f"_{idiom['text']}_ — {idiom['translation']}\n"
        f"_{idiom['example']}_\n\n"
        f"📖 **Mini-story:**\n"
        f"_{lesson['mini_story']}_\n"
        f"_{lesson['mini_story_ua']}_"
    )

    keyboard = [
        [
            InlineKeyboardButton("🧠 Тест", callback_data="quiz_now"),
            InlineKeyboardButton("💡 Пояснення", callback_data="explain_word"),
        ],
        [
            InlineKeyboardButton("📝 Ще приклади", callback_data="more_examples"),
            InlineKeyboardButton("✅ Вивчив!", callback_data="mark_learned"),
        ],
        [InlineKeyboardButton("⏭ Наступний урок", callback_data="next_lesson")],
    ]

    if edit_message:
        await edit_message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await ctx.bot.send_message(chat_id, text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def cmd_today(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await send_lesson(update.effective_chat.id, update.effective_user.id, ctx)

async def cb_start_lesson(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await send_lesson(query.message.chat_id, query.from_user.id, ctx, edit_message=query.message)

async def cb_next_lesson(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("⏳ Генерую наступний урок...")
    await send_lesson(query.message.chat_id, query.from_user.id, ctx, edit_message=query.message)

# ======= QUIZ =======

async def send_quiz(chat_id: int, user_id: int, ctx: ContextTypes.DEFAULT_TYPE, from_callback=None):
    u = get_user(user_id)
    lesson = u.get("current_lesson")

    if not lesson:
        await ctx.bot.send_message(chat_id, "Спочатку пройди урок! Напиши /today")
        return

    quiz = lesson["quiz"]
    answers_kb = []
    for i, ans in enumerate(quiz["answers"]):
        answers_kb.append([InlineKeyboardButton(ans, callback_data=f"quiz_answer_{i}")])

    text = f"🧠 **Тест:**\n\n{quiz['question']}"
    if from_callback:
        await from_callback.edit_text(text, reply_markup=InlineKeyboardMarkup(answers_kb), parse_mode="Markdown")
    else:
        await ctx.bot.send_message(chat_id, text, reply_markup=InlineKeyboardMarkup(answers_kb), parse_mode="Markdown")

async def cmd_quiz(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await send_quiz(update.effective_chat.id, update.effective_user.id, ctx)

async def cb_quiz_now(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await send_quiz(query.message.chat_id, query.from_user.id, ctx, from_callback=query.message)

async def cb_quiz_answer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    answer_idx = int(query.data.replace("quiz_answer_", ""))
    u = get_user(user_id)
    lesson = u.get("current_lesson")

    if not lesson:
        await query.answer("Спочатку пройди урок!")
        return

    correct = lesson["quiz"]["correct"]
    correct_text = lesson["quiz"]["answers"][correct]

    if answer_idx == correct:
        u["xp"] += 15
        text = f"✅ **Правильно!** +15 XP 🎉\n\n_{correct_text}_ — правильна відповідь!"
        await query.answer("✅ Правильно! +15 XP")
    else:
        text = f"❌ **Не так**\n\nПравильна відповідь: _{correct_text}_\nНе засмучуйся — повторення це теж навчання! 💪"
        await query.answer("❌ Спробуй ще")

    keyboard = [[
        InlineKeyboardButton("📚 Урок знову", callback_data="start_lesson"),
        InlineKeyboardButton("📊 Прогрес", callback_data="show_progress"),
    ]]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ======= КНОПКИ =======

async def cb_more_examples(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("⏳ Генерую...")
    u = get_user(query.from_user.id)
    lesson = u.get("current_lesson")
    if not lesson:
        await query.answer("Спочатку пройди урок!")
        return
    word = lesson["words"][0]["word"]
    explanation = await ai_explain(word)
    keyboard = [[InlineKeyboardButton("◀️ Назад до уроку", callback_data="start_lesson")]]
    await query.message.edit_text(
        f"💡 **{word}** — детальніше:\n\n{explanation}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def cb_explain_word(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("⏳ AI пояснює...")
    u = get_user(query.from_user.id)
    lesson = u.get("current_lesson")
    if not lesson:
        await query.answer("Спочатку пройди урок!")
        return
    words_list = ", ".join(w["word"] for w in lesson["words"])
    explanation = await ai_explain(words_list, "поясни різницю між ними і коли вживати")
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="start_lesson")]]
    await query.message.edit_text(
        f"🤖 **AI пояснює:**\n\n{explanation}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def cb_mark_learned(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    u = get_user(user_id)
    lesson = u.get("current_lesson")
    if lesson:
        for w in lesson["words"]:
            if w["word"] not in u["words_learned"]:
                u["words_learned"].append(w["word"])
        u["xp"] += 20
    await query.answer("✅ Слова збережено! +20 XP")
    keyboard = [[
        InlineKeyboardButton("⏭ Наступний урок", callback_data="next_lesson"),
        InlineKeyboardButton("📊 Прогрес", callback_data="show_progress"),
    ]]
    await query.message.edit_text(
        f"✅ Слова збережено у твій словник!\n\n"
        f"📚 Всього вивчено: **{len(u['words_learned'])}** слів\n"
        f"⭐ XP: **{u['xp']}**\n"
        f"🔥 Streak: **{u['streak']} днів**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ======= ПРОГРЕС =======

async def show_progress_text(user_id: int, first_name: str) -> tuple[str, InlineKeyboardMarkup]:
    u = get_user(user_id)
    xp = u["xp"]
    if xp >= 1000: rank = "👑 Майстер"
    elif xp >= 500: rank = "💎 Експерт"
    elif xp >= 200: rank = "🔥 Практик"
    elif xp >= 50:  rank = "⚡ Учень"
    else:           rank = "🌱 Новачок"

    text = (
        f"📊 **Прогрес: {first_name}**\n"
        f"━━━━━━━━━━━━━━━━━\n\n"
        f"{rank}\n\n"
        f"🔥 Streak: **{u['streak']} днів**\n"
        f"📚 Уроків: **{u['total_lessons']}**\n"
        f"💾 Слів вивчено: **{len(u['words_learned'])}**\n"
        f"⭐ XP: **{xp}**\n\n"
        f"📈 Рівень: **{u.get('level', '?')}**\n"
        f"🎯 Тема: **{u.get('topic', '?')}**"
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("📚 Урок дня", callback_data="start_lesson"),
        InlineKeyboardButton("🧠 Тест", callback_data="quiz_now"),
    ]])
    return text, keyboard

async def cmd_progress(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text, kb = await show_progress_text(update.effective_user.id, update.effective_user.first_name)
    await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")

async def cb_show_progress(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text, kb = await show_progress_text(query.from_user.id, query.from_user.first_name)
    await query.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

# ======= /help =======

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 **Команди:**\n\n"
        "/start — початок, вибір рівня\n"
        "/today — урок дня\n"
        "/quiz — тест\n"
        "/progress — мій прогрес\n"
        "/help — ця довідка\n\n"
        "💬 Або просто напиши будь-яке слово — AI поясню!",
        parse_mode="Markdown"
    )

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Якщо написали текст — AI пояснює слово."""
    word = update.message.text.strip()
    if len(word) > 50:
        return
    await update.message.reply_text("⏳ AI пояснює...")
    explanation = await ai_explain(word)
    await update.message.reply_text(f"💡 **{word}:**\n\n{explanation}", parse_mode="Markdown")

# ======= MAIN =======

async def setup_commands(app: Application):
    await app.bot.set_my_commands([
        BotCommand("start", "Почати / вибір рівня"),
        BotCommand("today", "Урок дня"),
        BotCommand("quiz", "Тест"),
        BotCommand("progress", "Мій прогрес"),
        BotCommand("help", "Допомога"),
    ])

def main():
    app = Application.builder().token(BOT_TOKEN).post_init(setup_commands).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CommandHandler("quiz", cmd_quiz))
    app.add_handler(CommandHandler("progress", cmd_progress))
    app.add_handler(CommandHandler("help", cmd_help))

    app.add_handler(CallbackQueryHandler(cb_level, pattern="^level_"))
    app.add_handler(CallbackQueryHandler(cb_topic, pattern="^topic_"))
    app.add_handler(CallbackQueryHandler(cb_start_lesson, pattern="^start_lesson$"))
    app.add_handler(CallbackQueryHandler(cb_next_lesson, pattern="^next_lesson$"))
    app.add_handler(CallbackQueryHandler(cb_quiz_now, pattern="^quiz_now$"))
    app.add_handler(CallbackQueryHandler(cb_quiz_answer, pattern="^quiz_answer_"))
    app.add_handler(CallbackQueryHandler(cb_more_examples, pattern="^more_examples$"))
    app.add_handler(CallbackQueryHandler(cb_explain_word, pattern="^explain_word$"))
    app.add_handler(CallbackQueryHandler(cb_mark_learned, pattern="^mark_learned$"))
    app.add_handler(CallbackQueryHandler(cb_show_progress, pattern="^show_progress$"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("🤖 Бот запущено! Ctrl+C для зупинки.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
