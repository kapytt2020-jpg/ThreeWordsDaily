"""
@YourBot_prod_bot — Автономний аналітик ThreeWordsDaily
Моніторить активність групи, генерує ідеї для контенту,
обговорює стратегію з адміном, пропонує покращення 24/7
"""
import asyncio, json, logging, sqlite3, random
from pathlib import Path
from datetime import datetime, date, timedelta
from openai import AsyncOpenAI
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

_creds     = json.loads(Path("credentials.local.json").read_text())
TOKEN      = _creds["telegram_bots"]["YourBot_prod_bot"]
OPENAI_KEY = _creds["openai_api_key"]
ADMIN_ID   = 1371213874
GROUP_ID   = -1002680027938
DB_FILE    = "users.db"

logging.basicConfig(format="%(asctime)s [Analyst] %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)
ai  = AsyncOpenAI(api_key=OPENAI_KEY)

# ─── SYSTEM PROMPT ─────────────────────────────────────────
ANALYST_SYSTEM = """Ти — аналітик і стратег Telegram-групи @ThreeWordsDailyChat.

РОЛЬ:
• Аналізуєш дані групи (кількість юзерів, активність, XP статистику)
• Пропонуєш ідеї для контенту на наступні дні
• Радиш як збільшити залученість і утримати юзерів
• Ідентифікуєш проблеми і пропонуєш рішення

СТИЛЬ:
• Відповідаєш українською
• Конкретні пропозиції з поясненням ЧОМУ це спрацює
• Короткі bullet-points, не довгі тексти
• HTML: <b>, <i>, <code>
• Ти розмовляєш тільки з адміном (власником групи)"""

CONTENT_IDEAS_PROMPT = """Проаналізуй статистику групи і запропонуй контент-план на завтра.

Дані групи:
{stats}

Запропонуй:
1. Тему для ранкового посту (9:00) — яке слово/правило/ідіом
2. Ідею для денного посту (13:00)
3. Тему вечірнього повторення (19:00)
4. Одну фічу/зміну яка підвищить залученість

Будь конкретним. Наприклад: "Слово: RESILIENT — воно зараз популярне в LinkedIn постах"."""

GROWTH_PROMPT = """Проаналізуй поточний стан групи і дай 3 конкретні поради для росту.

Дані:
{stats}

Фокусуйся на:
- Чому юзери йдуть (churn)
- Що привертає нових
- Який контент дає найбільше реакцій"""

# ─── DB HELPERS ────────────────────────────────────────────
def get_stats() -> dict:
    try:
        c = sqlite3.connect(DB_FILE, timeout=10)
        today = str(date.today())
        yesterday = str(date.today() - timedelta(days=1))
        total   = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        active_today = c.execute("SELECT COUNT(*) FROM users WHERE last_active=?", (today,)).fetchone()[0]
        active_week  = c.execute("SELECT COUNT(*) FROM users WHERE last_active >= ?",
                                  (str(date.today() - timedelta(days=7)),)).fetchone()[0]
        avg_xp  = c.execute("SELECT AVG(xp) FROM users").fetchone()[0] or 0
        avg_streak = c.execute("SELECT AVG(streak) FROM users").fetchone()[0] or 0
        top3    = c.execute("SELECT first_name, xp, streak FROM users ORDER BY xp DESC LIMIT 3").fetchall()
        s_today = c.execute("SELECT messages, new_u, quizzes FROM daily_stats WHERE dt=?",
                            (today,)).fetchone() or (0, 0, 0)
        s_yest  = c.execute("SELECT messages, new_u, quizzes FROM daily_stats WHERE dt=?",
                            (yesterday,)).fetchone() or (0, 0, 0)
        saved_words = c.execute("SELECT COUNT(*) FROM saved_words").fetchone()[0]
        c.close()
        return {
            "total_users": total,
            "active_today": active_today,
            "active_week": active_week,
            "avg_xp": round(avg_xp, 1),
            "avg_streak": round(avg_streak, 1),
            "top3": top3,
            "messages_today": s_today[0],
            "new_users_today": s_today[1],
            "quizzes_today": s_today[2],
            "messages_yesterday": s_yest[0],
            "new_users_yesterday": s_yest[1],
            "saved_words_total": saved_words,
        }
    except Exception as e:
        log.error(f"DB stats: {e}")
        return {}

def format_stats(stats: dict) -> str:
    if not stats: return "Дані недоступні"
    top3_str = ", ".join([f"{r[0]}({r[1]}XP)" for r in stats.get("top3", [])])
    return (
        f"Всього юзерів: {stats['total_users']}\n"
        f"Активних сьогодні: {stats['active_today']}\n"
        f"Активних за тиждень: {stats['active_week']}\n"
        f"Середній XP: {stats['avg_xp']}\n"
        f"Середня серія: {stats['avg_streak']} днів\n"
        f"ТОП-3: {top3_str}\n"
        f"Повідомлень сьогодні: {stats['messages_today']} (вчора: {stats['messages_yesterday']})\n"
        f"Нових юзерів сьогодні: {stats['new_users_today']}\n"
        f"Quiz сьогодні: {stats['quizzes_today']}\n"
        f"Збережених слів (всього): {stats['saved_words_total']}"
    )

# ─── AI ────────────────────────────────────────────────────
async def ask_analyst(prompt: str) -> str:
    try:
        r = await ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": ANALYST_SYSTEM},
                      {"role": "user", "content": prompt}],
            max_tokens=600, temperature=0.7)
        return r.choices[0].message.content.strip()
    except Exception as e:
        log.error(f"OpenAI: {e}")
        return "Помилка аналізу 😅"

# ─── COMMANDS ──────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    await update.message.reply_html(
        "🤖 <b>Analyst Bot онлайн</b>\n\n"
        "Я аналізую @ThreeWordsDailyChat і допомагаю розвивати групу.\n\n"
        "📋 <b>Команди:</b>\n"
        "/stats — статистика групи зараз\n"
        "/ideas — ідеї контенту на завтра\n"
        "/growth — поради для росту\n"
        "/report — повний щоденний звіт\n\n"
        "💬 Або просто напиши — я проаналізую будь-яке питання про групу."
    )

async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    stats = get_stats()
    await update.message.reply_html(
        f"📊 <b>Статистика @ThreeWordsDailyChat</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👥 Всього юзерів: <b>{stats.get('total_users', '?')}</b>\n"
        f"✅ Активних сьогодні: <b>{stats.get('active_today', '?')}</b>\n"
        f"📅 Активних за тиждень: <b>{stats.get('active_week', '?')}</b>\n"
        f"⭐ Середній XP: {stats.get('avg_xp', '?')}\n"
        f"🔥 Середня серія: {stats.get('avg_streak', '?')} днів\n\n"
        f"📈 <b>Сьогодні:</b>\n"
        f"  💬 Повідомлень: {stats.get('messages_today', 0)}\n"
        f"  🆕 Нових юзерів: {stats.get('new_users_today', 0)}\n"
        f"  🧠 Quiz: {stats.get('quizzes_today', 0)}\n"
        f"  📚 Слів збережено (всього): {stats.get('saved_words_total', 0)}"
    )

async def cmd_ideas(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    msg = await update.message.reply_text("🤔 Аналізую і генерую ідеї...")
    stats = get_stats()
    prompt = CONTENT_IDEAS_PROMPT.format(stats=format_stats(stats))
    reply  = await ask_analyst(prompt)
    await msg.edit_text(f"💡 <b>Контент-план на завтра:</b>\n\n{reply}", parse_mode="HTML")

async def cmd_growth(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    msg = await update.message.reply_text("📈 Аналізую можливості росту...")
    stats = get_stats()
    prompt = GROWTH_PROMPT.format(stats=format_stats(stats))
    reply  = await ask_analyst(prompt)
    await msg.edit_text(f"🚀 <b>Стратегія росту:</b>\n\n{reply}", parse_mode="HTML")

async def cmd_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    msg = await update.message.reply_text("📋 Формую повний звіт...")
    stats  = get_stats()
    prompt = (
        f"Зроби повний аналітичний звіт групи @ThreeWordsDailyChat.\n\n"
        f"Дані:\n{format_stats(stats)}\n\n"
        f"Включи:\n"
        f"1. Загальний стан (добре/погано)\n"
        f"2. Тренди (ростемо чи падаємо)\n"
        f"3. Топ-3 проблеми\n"
        f"4. Топ-3 можливості\n"
        f"5. Що зробити цього тижня"
    )
    reply = await ask_analyst(prompt)
    await msg.edit_text(f"📊 <b>Звіт за {date.today()}</b>\n\n{reply}", parse_mode="HTML")

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    if update.effective_user.id != ADMIN_ID: return
    if update.effective_chat.type != "private": return
    msg   = await update.message.reply_text("🤔 Аналізую...")
    stats = get_stats()
    prompt = (
        f"Питання адміна: {update.message.text}\n\n"
        f"Поточна статистика групи:\n{format_stats(stats)}"
    )
    reply = await ask_analyst(prompt)
    await msg.edit_text(reply, parse_mode="HTML")

# ─── AUTO ANALYSIS (кожні 6 годин) ────────────────────────
async def auto_analysis(app):
    sent_hours = set()
    while True:
        now = datetime.now()
        hour = now.hour
        # Відправляє аналіз о 8:00 і 20:00
        if hour in (8, 20) and hour not in sent_hours:
            try:
                stats  = get_stats()
                prompt = (
                    f"Короткий авто-звіт групи для адміна. Час: {now.strftime('%H:%M')}.\n"
                    f"Дані:\n{format_stats(stats)}\n\n"
                    f"3 речення: що добре, що турбує, що зробити зараз."
                )
                reply = await ask_analyst(prompt)
                await app.bot.send_message(
                    ADMIN_ID,
                    f"🤖 <b>Авто-аналіз {now.strftime('%H:%M')}</b>\n\n{reply}",
                    parse_mode="HTML"
                )
                sent_hours.add(hour)
                log.info(f"✅ Авто-аналіз відправлено ({hour}:00)")
            except Exception as e:
                log.error(f"Auto analysis: {e}")
        # скидаємо лічильник опівночі
        if hour == 0:
            sent_hours.clear()
        await asyncio.sleep(300)  # перевіряємо кожні 5 хвилин

# ─── MAIN ──────────────────────────────────────────────────
async def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("stats",  cmd_stats))
    app.add_handler(CommandHandler("ideas",  cmd_ideas))
    app.add_handler(CommandHandler("growth", cmd_growth))
    app.add_handler(CommandHandler("report", cmd_report))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    log.info("✅ @YourBot_prod_bot (Analyst) онлайн")

    asyncio.create_task(auto_analysis(app))
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
