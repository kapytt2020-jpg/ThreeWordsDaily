"""
analyst_bot.py — ADMIN ANALYST BOT

Private-chat bot for the admin. Reads real data from threewords.db,
generates AI analysis of group performance, content ideas, and growth strategy.
Auto-reports at 08:00 and 20:00 Kyiv time.

Environment variables (.env):
  ANALYST_BOT_TOKEN   — bot token for the analyst bot
  OPENAI_API_KEY      — OpenAI key
  ADMIN_CHAT_ID       — Telegram user ID of the admin (private chat)

Run:
  python3 analyst_bot.py
"""

import asyncio
import logging
import os
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

try:
    from content_plan_9months import get_current_week_plan, get_month_overview
    _CURRICULUM_AVAILABLE = True
except ImportError:
    _CURRICULUM_AVAILABLE = False

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

ANALYST_BOT_TOKEN: str = os.getenv("ANALYST_BOT_TOKEN", "")
if not ANALYST_BOT_TOKEN:
    raise RuntimeError("ANALYST_BOT_TOKEN is not set in .env")

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
ADMIN_CHAT_ID: int = int(os.getenv("ADMIN_CHAT_ID", "0"))
if not ADMIN_CHAT_ID:
    raise RuntimeError("ADMIN_CHAT_ID is not set in .env")

# Path to the same DB used by learning_bot + miniapp
DB_FILE: str = str(
    Path(__file__).parent / "miniapp" / "threewords.db"
)

logging.basicConfig(
    format="%(asctime)s [analyst_bot] %(levelname)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("analyst_bot")

ai = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ---------------------------------------------------------------------------
# AI prompts
# ---------------------------------------------------------------------------

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
• Розмовляєш тільки з адміном (власником групи)"""

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

# ---------------------------------------------------------------------------
# DB helpers  (reads threewords.db — same schema as database.py)
# ---------------------------------------------------------------------------

def get_stats() -> dict:
    """Read live metrics from threewords.db. Returns empty dict on error."""
    if not Path(DB_FILE).exists():
        log.warning("DB not found at %s", DB_FILE)
        return {}
    try:
        conn = sqlite3.connect(DB_FILE, timeout=10)
        today = str(date.today())
        week_ago = str(date.today() - timedelta(days=7))

        total = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        active_today = conn.execute(
            "SELECT COUNT(*) FROM users WHERE last_lesson_date = ?", (today,)
        ).fetchone()[0]
        active_week = conn.execute(
            "SELECT COUNT(*) FROM users WHERE last_lesson_date >= ?", (week_ago,)
        ).fetchone()[0]
        avg_xp = conn.execute("SELECT AVG(xp) FROM users").fetchone()[0] or 0
        avg_streak = conn.execute("SELECT AVG(streak) FROM users").fetchone()[0] or 0
        top3 = conn.execute(
            "SELECT first_name, xp, streak FROM users ORDER BY xp DESC LIMIT 3"
        ).fetchall()
        new_today = conn.execute(
            "SELECT COUNT(*) FROM users WHERE registered_at = ?", (today,)
        ).fetchone()[0]
        conn.close()

        yesterday = str(date.today() - timedelta(days=1))
        month_ago = str(date.today() - timedelta(days=30))

        active_yesterday = conn.execute(
            "SELECT COUNT(*) FROM users WHERE last_lesson_date = ?", (yesterday,)
        ).fetchone()[0]
        active_month = conn.execute(
            "SELECT COUNT(*) FROM users WHERE last_lesson_date >= ?", (month_ago,)
        ).fetchone()[0]
        new_week = conn.execute(
            "SELECT COUNT(*) FROM users WHERE registered_at >= ?", (week_ago,)
        ).fetchone()[0]
        top10 = conn.execute(
            "SELECT first_name, xp, streak FROM users ORDER BY xp DESC LIMIT 10"
        ).fetchall()
        streak_dist = conn.execute(
            "SELECT CASE "
            "  WHEN streak=0 THEN '0' "
            "  WHEN streak<=3 THEN '1-3' "
            "  WHEN streak<=7 THEN '4-7' "
            "  WHEN streak<=30 THEN '8-30' "
            "  ELSE '30+' END as bucket, COUNT(*) "
            "FROM users GROUP BY bucket"
        ).fetchall()
        conn.close()

        return {
            "total_users": total,
            "active_today": active_today,
            "active_yesterday": active_yesterday,
            "active_week": active_week,
            "active_month": active_month,
            "avg_xp": round(avg_xp, 1),
            "avg_streak": round(avg_streak, 1),
            "top3": top3,
            "top10": top10,
            "new_users_today": new_today,
            "new_users_week": new_week,
            "streak_distribution": dict(streak_dist),
        }
    except Exception as exc:
        log.error("DB stats error: %s", exc)
        return {}


def format_stats(stats: dict) -> str:
    if not stats:
        return "Дані недоступні"
    top3_str = ", ".join(
        f"{r[0] or 'Unknown'}({r[1]}XP/streak{r[2]})" for r in stats.get("top3", [])
    )
    return (
        f"Всього юзерів: {stats['total_users']}\n"
        f"Активних сьогодні: {stats['active_today']}\n"
        f"Активних за тиждень: {stats['active_week']}\n"
        f"Нових сьогодні: {stats['new_users_today']}\n"
        f"Середній XP: {stats['avg_xp']}\n"
        f"Середня серія: {stats['avg_streak']} днів\n"
        f"ТОП-3: {top3_str}"
    )


# ---------------------------------------------------------------------------
# AI helper
# ---------------------------------------------------------------------------

async def ask_analyst(prompt: str) -> str:
    try:
        r = await ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": ANALYST_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            max_tokens=600,
            temperature=0.7,
        )
        return r.choices[0].message.content.strip()
    except Exception as exc:
        log.error("OpenAI error: %s", exc)
        return "Помилка аналізу 😅"


# ---------------------------------------------------------------------------
# Command handlers (admin only)
# ---------------------------------------------------------------------------

def _is_admin(update: Update) -> bool:
    return update.effective_user is not None and update.effective_user.id == ADMIN_CHAT_ID


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    await update.message.reply_html(
        "🤖 <b>Analyst Bot онлайн</b>\n\n"
        "Читаю реальні дані з threewords.db і аналізую групу.\n\n"
        "📋 <b>Команди:</b>\n"
        "/stats — статистика зараз\n"
        "/retention — DAU/WAU/MAU + розподіл стріків\n"
        "/top — ТОП-10 гравців\n"
        "/ideas — ідеї контенту на завтра\n"
        "/curriculum — поточний тиждень навчання\n"
        "/weekly — тижневий звіт\n"
        "/growth — поради для росту\n"
        "/report — повний аналітичний звіт\n\n"
        "💬 Або просто напиши питання — проаналізую будь-що."
    )


async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    stats = get_stats()
    if not stats:
        await update.message.reply_text("⚠️ Не вдалося прочитати дані з БД.")
        return
    await update.message.reply_html(
        f"📊 <b>Статистика @ThreeWordsDailyChat</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👥 Всього юзерів: <b>{stats['total_users']}</b>\n"
        f"✅ Активних сьогодні: <b>{stats['active_today']}</b>\n"
        f"📅 Активних за тиждень: <b>{stats['active_week']}</b>\n"
        f"🆕 Нових сьогодні: <b>{stats['new_users_today']}</b>\n"
        f"⭐ Середній XP: {stats['avg_xp']}\n"
        f"🔥 Середня серія: {stats['avg_streak']} днів"
    )


async def cmd_ideas(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    msg = await update.message.reply_text("🤔 Аналізую і генерую ідеї...")
    stats = get_stats()
    prompt = CONTENT_IDEAS_PROMPT.format(stats=format_stats(stats))
    reply = await ask_analyst(prompt)
    await msg.edit_text(
        f"💡 <b>Контент-план на завтра:</b>\n\n{reply}",
        parse_mode="HTML",
    )


async def cmd_growth(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    msg = await update.message.reply_text("📈 Аналізую можливості росту...")
    stats = get_stats()
    prompt = GROWTH_PROMPT.format(stats=format_stats(stats))
    reply = await ask_analyst(prompt)
    await msg.edit_text(
        f"🚀 <b>Стратегія росту:</b>\n\n{reply}",
        parse_mode="HTML",
    )


async def cmd_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    msg = await update.message.reply_text("📋 Формую повний звіт...")
    stats = get_stats()
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
    await msg.edit_text(
        f"📊 <b>Звіт за {date.today()}</b>\n\n{reply}",
        parse_mode="HTML",
    )


async def cmd_retention(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    stats = get_stats()
    if not stats:
        await update.message.reply_text("⚠️ Дані недоступні.")
        return
    total = stats["total_users"] or 1
    r7  = round(stats["active_week"]  / total * 100, 1)
    r30 = round(stats["active_month"] / total * 100, 1)
    dau = round(stats["active_today"] / total * 100, 1)
    dau_prev = round(stats["active_yesterday"] / total * 100, 1)
    trend = "📈" if stats["active_today"] >= stats["active_yesterday"] else "📉"

    dist = stats.get("streak_distribution", {})
    dist_str = "  ".join(f"{k}д: {v}" for k, v in sorted(dist.items()))

    await update.message.reply_html(
        f"📊 <b>Retention @ThreeWordsDailyChat</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"DAU вчора: <b>{stats['active_yesterday']}</b> ({dau_prev}%)\n"
        f"DAU сьогодні: <b>{stats['active_today']}</b> ({dau}%) {trend}\n"
        f"WAU (7д): <b>{stats['active_week']}</b> ({r7}%)\n"
        f"MAU (30д): <b>{stats['active_month']}</b> ({r30}%)\n"
        f"Нових за тиждень: <b>{stats['new_users_week']}</b>\n\n"
        f"🔥 <b>Розподіл стріків:</b>\n{dist_str}"
    )


async def cmd_top(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    stats = get_stats()
    if not stats or not stats.get("top10"):
        await update.message.reply_text("⚠️ Дані недоступні.")
        return
    medals = ["🥇", "🥈", "🥉"] + ["4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    lines = ["🏆 <b>ТОП-10 гравців</b>\n━━━━━━━━━━━━━━━"]
    for i, (name, xp, streak) in enumerate(stats["top10"]):
        lines.append(f"{medals[i]} {name or 'Unknown'} — {xp} XP 🔥{streak}д")
    await update.message.reply_html("\n".join(lines))


async def cmd_curriculum(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    if not _CURRICULUM_AVAILABLE:
        await update.message.reply_text("⚠️ content_plan_9months.py not found.")
        return
    plan = get_current_week_plan()
    if not plan:
        await update.message.reply_text("Немає плану для поточного тижня.")
        return
    words_preview = "\n".join(
        f"  • <b>{w['en']}</b> — {w['ua']}" for w in plan["words"][:5]
    )
    await update.message.reply_html(
        f"📅 <b>Поточний тиждень</b>\n"
        f"Місяць {plan['month']}, тиждень {plan['week']}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🎯 <b>Тема:</b> {plan['theme']}\n"
        f"📚 <b>Граматика:</b> {plan['grammar']}\n"
        f"💬 <b>Ідіома:</b> <i>{plan['idiom']}</i>\n"
        f"   {plan['idiom_meaning']}\n\n"
        f"📝 <b>Перші 5 слів тижня:</b>\n{words_preview}\n\n"
        f"✍️ <b>Міністорія:</b>\n<i>{plan['mini_story_prompt']}</i>"
    )


async def cmd_weekly(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    msg = await update.message.reply_text("📋 Формую тижневий звіт...")
    stats = get_stats()
    curriculum_info = ""
    if _CURRICULUM_AVAILABLE:
        plan = get_current_week_plan()
        if plan:
            curriculum_info = (
                f"\nПоточна тема навчання: {plan['theme']}\n"
                f"Граматика тижня: {plan['grammar']}"
            )
    prompt = (
        f"Зроби ТИЖНЕВИЙ звіт @ThreeWordsDailyChat для адміна.\n\n"
        f"Дані:\n{format_stats(stats)}{curriculum_info}\n\n"
        f"Формат:\n"
        f"1. Що вдалося цього тижня\n"
        f"2. Що не вдалося\n"
        f"3. Топ-3 дії на наступний тиждень\n"
        f"4. Прогноз активності на наступний тиждень"
    )
    reply = await ask_analyst(prompt)
    await msg.edit_text(
        f"📋 <b>Тижневий звіт</b>\n\n{reply}",
        parse_mode="HTML",
    )


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    if not _is_admin(update):
        return
    if update.effective_chat.type != "private":
        return
    msg = await update.message.reply_text("🤔 Аналізую...")
    stats = get_stats()
    prompt = (
        f"Питання адміна: {update.message.text}\n\n"
        f"Поточна статистика групи:\n{format_stats(stats)}"
    )
    reply = await ask_analyst(prompt)
    await msg.edit_text(reply, parse_mode="HTML")


# ---------------------------------------------------------------------------
# Auto-report task: runs at 08:00 and 20:00 Kyiv time
# ---------------------------------------------------------------------------

async def _auto_report_loop(app: Application) -> None:
    """Send a brief auto-analysis to admin at 08:00 and 20:00."""
    sent_hours: set[int] = set()
    while True:
        now = datetime.now()
        hour = now.hour
        if hour in (8, 20) and hour not in sent_hours:
            try:
                stats = get_stats()
                prompt = (
                    f"Короткий авто-звіт групи для адміна. "
                    f"Час: {now.strftime('%H:%M')}.\n"
                    f"Дані:\n{format_stats(stats)}\n\n"
                    "Дай 3 bullet-points: що важливо зараз."
                )
                reply = await ask_analyst(prompt)
                await app.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=f"🤖 <b>Авто-аналіз {now.strftime('%H:%M')}</b>\n\n{reply}",
                    parse_mode="HTML",
                )
                sent_hours.add(hour)
                log.info("Auto-report sent for hour %d", hour)
            except Exception as exc:
                log.error("Auto-report failed: %s", exc)
        # Reset sent_hours at start of new day
        if hour == 0:
            sent_hours.clear()
        await asyncio.sleep(60)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    app = Application.builder().token(ANALYST_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",      cmd_start))
    app.add_handler(CommandHandler("stats",      cmd_stats))
    app.add_handler(CommandHandler("retention",  cmd_retention))
    app.add_handler(CommandHandler("top",        cmd_top))
    app.add_handler(CommandHandler("ideas",      cmd_ideas))
    app.add_handler(CommandHandler("curriculum", cmd_curriculum))
    app.add_handler(CommandHandler("weekly",     cmd_weekly))
    app.add_handler(CommandHandler("growth",     cmd_growth))
    app.add_handler(CommandHandler("report",     cmd_report))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    log.info("analyst_bot is online (admin_id=%d)", ADMIN_CHAT_ID)

    asyncio.create_task(_auto_report_loop(app))
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
