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
import random
import sqlite3
import subprocess
import time
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
        "📋 <b>Аналітика:</b>\n"
        "/stats — статистика зараз\n"
        "/retention — DAU/WAU/MAU\n"
        "/top — ТОП-10 гравців\n"
        "/users — всі юзери з ID\n"
        "/raffle [N] [active/streak5] — розіграш 🎲\n"
        "/weekly — тижневий AI звіт\n"
        "/growth — поради для росту\n"
        "/report — повний звіт\n\n"
        "🖥 <b>Управління сервісами:</b>\n"
        "/status — статус всіх 8 сервісів\n"
        "/restart [сервіс|all] — перезапуск\n"
        "/logs [сервіс] — останні рядки логу\n"
        "/killport — звільнити порт 8000 + restart miniapp\n\n"
        "Сервіси: learning, content, teacher, analyst, marketer, speak, miniapp, watchdog\n\n"
        "💬 Або просто напиши питання."
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


# ---------------------------------------------------------------------------
# Raffle / Giveaway helpers
# ---------------------------------------------------------------------------

def get_all_users_for_raffle(filter_type: str = "all", min_streak: int = 0) -> list[dict]:
    """
    Returns list of dicts: tg_id, first_name, username, xp, streak, last_lesson_date.
    filter_type: 'all' | 'active_7' | 'active_30' | 'streak'
    """
    if not Path(DB_FILE).exists():
        return []
    try:
        conn = sqlite3.connect(DB_FILE, timeout=10)
        today = str(date.today())
        week_ago = str(date.today() - timedelta(days=7))
        month_ago = str(date.today() - timedelta(days=30))

        if filter_type == "active_7":
            rows = conn.execute(
                "SELECT tg_id, first_name, username, xp, streak, last_lesson_date "
                "FROM users WHERE last_lesson_date >= ? ORDER BY xp DESC",
                (week_ago,)
            ).fetchall()
        elif filter_type == "active_30":
            rows = conn.execute(
                "SELECT tg_id, first_name, username, xp, streak, last_lesson_date "
                "FROM users WHERE last_lesson_date >= ? ORDER BY xp DESC",
                (month_ago,)
            ).fetchall()
        elif filter_type == "streak":
            rows = conn.execute(
                "SELECT tg_id, first_name, username, xp, streak, last_lesson_date "
                "FROM users WHERE streak >= ? ORDER BY streak DESC",
                (min_streak,)
            ).fetchall()
        else:  # all
            rows = conn.execute(
                "SELECT tg_id, first_name, username, xp, streak, last_lesson_date "
                "FROM users ORDER BY xp DESC"
            ).fetchall()
        conn.close()

        return [
            {
                "tg_id": r[0], "first_name": r[1] or "Unknown",
                "username": r[2] or "", "xp": r[3] or 0,
                "streak": r[4] or 0, "last_lesson": r[5] or "—",
            }
            for r in rows
        ]
    except Exception as exc:
        log.error("Raffle DB error: %s", exc)
        return []


async def cmd_users(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Show full user list with IDs — for giveaway tracking."""
    if not _is_admin(update):
        return
    users = get_all_users_for_raffle("all")
    if not users:
        await update.message.reply_text("⚠️ Дані недоступні або 0 юзерів.")
        return

    # Send count summary first
    total = len(users)
    week_ago = str(date.today() - timedelta(days=7))
    active_7 = sum(1 for u in users if u["last_lesson"] >= week_ago)

    lines = [f"👥 <b>Всі юзери ({total})</b> | Активних 7д: {active_7}\n"]
    for i, u in enumerate(users[:50], 1):  # max 50 per message
        uname = f"@{u['username']}" if u["username"] else "—"
        lines.append(
            f"{i}. <code>{u['tg_id']}</code> | {u['first_name']} {uname} "
            f"| {u['xp']} XP 🔥{u['streak']}д"
        )

    if total > 50:
        lines.append(f"\n<i>...і ще {total-50} юзерів. Використай /users_csv для повного списку.</i>")

    text = "\n".join(lines)
    # Telegram limit: split if too long
    if len(text) > 4000:
        text = text[:4000] + "\n..."
    await update.message.reply_html(text)


async def cmd_raffle(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Pick random winner(s) for a giveaway.

    Usage:
      /raffle           — 1 winner from ALL users
      /raffle 3         — 3 winners from all
      /raffle active 3  — 3 winners active in last 7 days
      /raffle active30  — winners active in last 30 days
      /raffle streak5   — winners with streak >= 5
    """
    if not _is_admin(update):
        return

    args = ctx.args or []
    n_winners = 1
    filter_type = "all"
    min_streak = 0

    for arg in args:
        arg = arg.lower()
        if arg.isdigit():
            n_winners = min(int(arg), 50)
        elif arg in ("active", "active7", "7d"):
            filter_type = "active_7"
        elif arg in ("active30", "30d", "month"):
            filter_type = "active_30"
        elif arg.startswith("streak"):
            filter_type = "streak"
            try:
                min_streak = int(arg.replace("streak", "")) or 1
            except ValueError:
                min_streak = 3

    users = get_all_users_for_raffle(filter_type, min_streak)
    if not users:
        await update.message.reply_text("⚠️ Немає юзерів за цим фільтром.")
        return

    if len(users) < n_winners:
        n_winners = len(users)

    winners = random.sample(users, n_winners)

    filter_labels = {
        "all": "всіх юзерів", "active_7": "активних 7 днів",
        "active_30": "активних 30 днів", "streak": f"стрік ≥ {min_streak} днів",
    }
    pool_label = filter_labels.get(filter_type, "всіх")

    lines = [
        f"🎲 <b>Розіграш!</b>",
        f"Пул: {pool_label} ({len(users)} учасників)",
        f"Переможців: {n_winners}\n",
    ]

    medals = ["🥇", "🥈", "🥉"] + ["🎁"] * 50
    for i, w in enumerate(winners):
        uname = f"@{w['username']}" if w["username"] else "—"
        lines.append(
            f"{medals[i]} <b>{w['first_name']}</b> {uname}\n"
            f"   ID: <code>{w['tg_id']}</code> | {w['xp']} XP 🔥{w['streak']}д"
        )

    lines.append(f"\n<i>Розіграш проведено: {datetime.now().strftime('%d.%m.%Y %H:%M')}</i>")
    await update.message.reply_html("\n".join(lines))


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
    """
    Auto-reports:
      08:00 daily  — brief morning pulse
      20:00 daily  — brief evening pulse
      09:00 Monday — full weekly digest (admin's weekly review)
    """
    sent_hours: set[int] = set()
    weekly_sent_this_week: bool = False

    while True:
        now = datetime.now()
        hour = now.hour
        weekday = now.weekday()  # 0 = Monday

        # --- Weekly digest: Monday 09:00 ---
        if weekday == 0 and hour == 9 and not weekly_sent_this_week:
            try:
                stats = get_stats()
                curriculum_info = ""
                if _CURRICULUM_AVAILABLE:
                    plan = get_current_week_plan()
                    if plan:
                        curriculum_info = (
                            f"\nТема тижня: {plan['theme']}\n"
                            f"Граматика: {plan['grammar']}\n"
                            f"Ідіома: {plan['idiom']}"
                        )

                total = stats.get("total_users", 0)
                new_w = stats.get("new_users_week", 0)
                active_w = stats.get("active_week", 0)
                retention = round(active_w / total * 100, 1) if total else 0
                growth = round(new_w / max(total - new_w, 1) * 100, 1)

                prompt = (
                    f"ТИЖНЕВИЙ ДАЙДЖЕСТ для адміна @ThreeWordsDailyChat.\n\n"
                    f"Статистика:\n{format_stats(stats)}{curriculum_info}\n\n"
                    f"Retention тижня: {retention}% | Ріст: +{growth}%\n\n"
                    f"Зроби КОРОТКИЙ звіт (max 200 слів):\n"
                    f"1. 🟢 Що добре (1-2 пункти)\n"
                    f"2. 🔴 Що погано / ризики\n"
                    f"3. ✅ 3 конкретні дії на цей тиждень\n"
                    f"4. 📈 Прогноз до наступного понеділка"
                )
                reply = await ask_analyst(prompt)

                top3_lines = "\n".join(
                    f"  {i+1}. {r[0] or '?'} — {r[1]} XP 🔥{r[2]}д"
                    for i, r in enumerate(stats.get("top3", []))
                )

                await app.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=(
                        f"📋 <b>Тижневий дайджест — {now.strftime('%d.%m.%Y')}</b>\n"
                        f"━━━━━━━━━━━━━━━\n"
                        f"👥 Всього юзерів: <b>{total}</b>  (+{new_w} за тиждень)\n"
                        f"✅ Активних 7д: <b>{active_w}</b> ({retention}%)\n"
                        f"📅 Активних сьогодні: <b>{stats.get('active_today', 0)}</b>\n"
                        f"🔥 Середній стрік: {stats.get('avg_streak', 0)} днів\n\n"
                        f"🏆 <b>ТОП-3:</b>\n{top3_lines}\n\n"
                        f"🤖 <b>AI аналіз:</b>\n{reply}"
                    ),
                    parse_mode="HTML",
                )
                weekly_sent_this_week = True
                log.info("Weekly digest sent (Monday 09:00)")
            except Exception as exc:
                log.error("Weekly digest failed: %s", exc)

        # --- Daily pulse: 08:00 and 20:00 ---
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

        # Reset daily at midnight, weekly on Tuesday
        if hour == 0:
            sent_hours.clear()
            if weekday == 1:  # Tuesday midnight resets weekly flag
                weekly_sent_this_week = False

        await asyncio.sleep(55)


# ---------------------------------------------------------------------------
# Remote Management Commands
# ---------------------------------------------------------------------------

LAUNCHD_LABELS = {
    "learning":   "com.threewordsdaily.learning",
    "content":    "com.threewordsdaily.content",
    "teacher":    "com.threewordsdaily.teacher",
    "analyst":    "com.threewordsdaily.analyst",
    "marketer":   "com.threewordsdaily.marketer",
    "speak":      "com.threewordsdaily.speak",
    "miniapp":    "com.threewordsdaily.miniapp.v2",
    "watchdog":   "com.threewordsdaily.watchdog",
}
SERVICE_KEYWORDS = {
    "learning":  "learning_bot.py",
    "content":   "content_publisher.py",
    "teacher":   "teacher_bot.py",
    "analyst":   "analyst_bot.py",
    "marketer":  "marketer_bot.py",
    "speak":     "speak_bot.py",
    "miniapp":   "uvicorn",
    "watchdog":  "watchdog.py",
}
LOG_FILES = {
    "learning":  "logs/learning_bot.log",
    "content":   "logs/content_publisher.log",
    "teacher":   "logs/teacher_bot.log",
    "analyst":   "logs/analyst_bot_error.log",
    "marketer":  "logs/marketer_bot.log",
    "speak":     "logs/speak_bot.log",
    "miniapp":   "logs/miniapp.log",
    "watchdog":  "logs/watchdog.log",
}
BOT_DIR = Path(__file__).parent


def _proc_running(keyword: str) -> bool:
    r = subprocess.run(["pgrep", "-f", keyword], capture_output=True)
    return r.returncode == 0


def _kill_port_8000() -> None:
    try:
        r = subprocess.run(["lsof", "-ti", ":8000"], capture_output=True, text=True)
        for pid in r.stdout.strip().split():
            if pid.isdigit():
                subprocess.run(["kill", "-9", pid], capture_output=True)
    except Exception:
        pass


def _restart_service(name: str) -> str:
    label = LAUNCHD_LABELS.get(name)
    if not label:
        return f"❌ Невідомий сервіс: {name}"
    if name == "miniapp":
        _kill_port_8000()
        time.sleep(1)
    try:
        subprocess.run(
            ["/bin/launchctl", "kickstart", "-k", f"gui/{os.getuid()}/{label}"],
            capture_output=True, timeout=15
        )
        time.sleep(2)
        running = _proc_running(SERVICE_KEYWORDS[name])
        return f"✅ {name} перезапущено" if running else f"⚠️ {name} запущено але процес не знайдено"
    except Exception as exc:
        return f"❌ {name}: {exc}"


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Show live status of all services."""
    if not _is_admin(update):
        return
    lines = ["🖥 <b>Статус сервісів</b>\n"]
    for name, kw in SERVICE_KEYWORDS.items():
        icon = "✅" if _proc_running(kw) else "❌"
        lines.append(f"{icon} <code>{name}</code>")
    # Miniapp port check
    port_check = subprocess.run(["lsof", "-ti", ":8000"], capture_output=True, text=True)
    port_pid = port_check.stdout.strip()
    lines.append(f"\n🔌 Порт 8000: {'зайнятий PID ' + port_pid if port_pid else 'вільний'}")
    lines.append(f"\n🕐 {datetime.now().strftime('%H:%M:%S')}")
    await update.message.reply_html("\n".join(lines))


async def cmd_restart(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Restart one or all services. Usage: /restart miniapp | /restart all"""
    if not _is_admin(update):
        return
    args = ctx.args
    if not args:
        kb = [
            [f"/restart {n}" for n in list(LAUNCHD_LABELS.keys())[:4]],
            [f"/restart {n}" for n in list(LAUNCHD_LABELS.keys())[4:]],
            ["/restart all"],
        ]
        await update.message.reply_html(
            "⚙️ <b>Restart</b>\n\nВибери сервіс:\n" +
            "\n".join(" ".join(row) for row in kb)
        )
        return

    target = args[0].lower()
    if target == "all":
        await update.message.reply_text("⏳ Перезапускаю всі сервіси...")
        results = []
        for name in LAUNCHD_LABELS:
            if name == "analyst":
                continue  # don't restart self
            results.append(_restart_service(name))
        await update.message.reply_html("\n".join(results))
    elif target in LAUNCHD_LABELS:
        await update.message.reply_text(f"⏳ Перезапускаю {target}...")
        result = _restart_service(target)
        await update.message.reply_html(result)
    else:
        await update.message.reply_html(
            f"❓ Невідомий сервіс: <code>{target}</code>\n"
            f"Доступні: {', '.join(LAUNCHD_LABELS.keys())}"
        )


async def cmd_logs(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Show last 30 lines of a service log. Usage: /logs miniapp"""
    if not _is_admin(update):
        return
    args = ctx.args
    if not args or args[0].lower() not in LOG_FILES:
        await update.message.reply_html(
            "📋 <b>Логи</b>\n\nВикористання: <code>/logs [сервіс]</code>\n"
            "Сервіси: " + ", ".join(LOG_FILES.keys())
        )
        return
    name = args[0].lower()
    log_path = BOT_DIR / LOG_FILES[name]
    if not log_path.exists():
        await update.message.reply_text(f"❌ Лог не знайдено: {log_path}")
        return
    # Read last 40 lines
    try:
        lines = log_path.read_text(errors="replace").splitlines()
        tail = "\n".join(lines[-40:]) if len(lines) > 40 else "\n".join(lines)
        if len(tail) > 3800:
            tail = "..." + tail[-3800:]
        await update.message.reply_html(
            f"📋 <b>{name} — останні рядки</b>\n\n<pre>{tail}</pre>"
        )
    except Exception as exc:
        await update.message.reply_text(f"❌ Помилка читання логу: {exc}")


async def cmd_kill_port(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Kill process on port 8000 and restart miniapp."""
    if not _is_admin(update):
        return
    _kill_port_8000()
    time.sleep(1)
    result = _restart_service("miniapp")
    await update.message.reply_html(f"🔌 Порт 8000 звільнено\n{result}")


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
    app.add_handler(CommandHandler("raffle",     cmd_raffle))
    app.add_handler(CommandHandler("draw",       cmd_raffle))
    app.add_handler(CommandHandler("users",      cmd_users))
    # Remote management
    app.add_handler(CommandHandler("status",     cmd_status))
    app.add_handler(CommandHandler("restart",    cmd_restart))
    app.add_handler(CommandHandler("logs",       cmd_logs))
    app.add_handler(CommandHandler("killport",   cmd_kill_port))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    log.info("analyst_bot is online (admin_id=%d)", ADMIN_CHAT_ID)

    asyncio.create_task(_auto_report_loop(app))
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
