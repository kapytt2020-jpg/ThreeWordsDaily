"""
analytics_planner.py — CONTENT_ANALYZER_PLANNER
Runs on schedule, reads real data from threewords.db and Google Sheets,
produces real analytics reports and content plans.

Schedule:
  Every 15 min  : collect metrics snapshot from DB + write to Sheets
  Sunday 20:00  : full weekly analytics report
  Sunday 23:00  : generate next week's content plan
"""

import asyncio
import json
import logging
import os
from datetime import date, datetime, timedelta
from typing import Optional

import aiosqlite
import httpx
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

# ======= CONFIG =======
LEARNING_BOT_TOKEN: str = os.getenv("LEARNING_BOT_TOKEN", "")
ADMIN_CHAT_ID: str = os.getenv("ADMIN_CHAT_ID", "")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
SHEETS_API_URL: str = os.getenv("SHEETS_API_URL", "")

DB_PATH: str = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "miniapp",
    "threewords.db",
)
ANALYTICS_LOG: str = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "analytics_log.jsonl",
)

logging.basicConfig(
    format="%(asctime)s [analytics_planner] %(levelname)s %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)


# ======= DB QUERIES =======

async def collect_db_snapshot() -> Optional[dict]:
    """Read live metrics from threewords.db. Returns None if DB is unavailable."""
    today = str(date.today())
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT COUNT(*) FROM users") as cur:
                row = await cur.fetchone()
                total_users: int = row[0] if row else 0

            async with db.execute(
                "SELECT COUNT(*) FROM users WHERE last_lesson_date = ?", (today,)
            ) as cur:
                row = await cur.fetchone()
                active_today: int = row[0] if row else 0

            async with db.execute(
                """SELECT COALESCE(SUM(pe.xp_earned), 0)
                   FROM progress_events pe
                   WHERE pe.created_at = ?""",
                (today,),
            ) as cur:
                row = await cur.fetchone()
                total_xp_today: int = row[0] if row else 0

            async with db.execute(
                "SELECT AVG(streak) FROM users WHERE streak > 0"
            ) as cur:
                row = await cur.fetchone()
                avg_streak: float = round(row[0], 2) if row and row[0] is not None else 0.0

        return {
            "timestamp": datetime.now().isoformat(),
            "date": today,
            "total_users": total_users,
            "active_today": active_today,
            "total_xp_today": total_xp_today,
            "avg_streak": avg_streak,
        }
    except Exception as exc:
        logger.error("DB snapshot failed: %s", exc)
        return None


# ======= SHEETS HELPERS =======

async def sheets_append_row(tab: str, row: dict) -> bool:
    """Append a row to the given Sheets tab. Returns True on success."""
    if not SHEETS_API_URL:
        return False
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{SHEETS_API_URL}/{tab}",
                json={"action": "append", "row": row},
            )
            resp.raise_for_status()
        return True
    except Exception as exc:
        logger.warning("Sheets append to %s failed: %s", tab, exc)
        return False


async def sheets_read(tab: str, params: Optional[dict] = None) -> list[dict]:
    """Read rows from a Sheets tab. Returns empty list on failure."""
    if not SHEETS_API_URL:
        return []
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{SHEETS_API_URL}/{tab}",
                params=params or {},
            )
            resp.raise_for_status()
            return resp.json().get("rows", [])
    except Exception as exc:
        logger.warning("Sheets read from %s failed: %s", tab, exc)
        return []


def _append_to_local_log(record: dict) -> None:
    """Fallback: append JSON record to local JSONL file."""
    try:
        with open(ANALYTICS_LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.error("Local log write failed: %s", exc)


# ======= TELEGRAM HELPER =======

async def send_telegram(text: str) -> None:
    """Send a plain-text message to ADMIN_CHAT_ID via the learning bot token."""
    if not LEARNING_BOT_TOKEN or not ADMIN_CHAT_ID:
        logger.warning("Cannot send Telegram message: token or chat_id not set.")
        logger.info("Message content:\n%s", text)
        return
    url = f"https://api.telegram.org/bot{LEARNING_BOT_TOKEN}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                url,
                json={"chat_id": ADMIN_CHAT_ID, "text": text},
            )
            resp.raise_for_status()
        logger.info("Telegram message sent to admin.")
    except Exception as exc:
        logger.error("Telegram send failed: %s", exc)


# ======= TASK 1: 15-MINUTE METRICS SNAPSHOT =======

async def task_metrics_snapshot() -> None:
    """Collect a lightweight metrics snapshot and write it to Sheets or local log."""
    logger.info("Collecting metrics snapshot...")

    snapshot = await collect_db_snapshot()
    if snapshot is None:
        logger.error("Snapshot skipped: DB unavailable.")
        return

    logger.info(
        "Snapshot: total_users=%d active_today=%d xp_today=%d avg_streak=%.2f",
        snapshot["total_users"],
        snapshot["active_today"],
        snapshot["total_xp_today"],
        snapshot["avg_streak"],
    )

    written = await sheets_append_row("content_metrics", snapshot)
    if not written:
        logger.warning("Sheets unavailable — writing snapshot to local log.")
        _append_to_local_log(snapshot)


# ======= TASK 2: SUNDAY 20:00 — WEEKLY ANALYTICS REPORT =======

def _compute_weekly_metrics(rows: list[dict]) -> dict:
    """Derive weekly KPIs from 7 days of content_metrics snapshots."""
    if not rows:
        return {}

    # Group by date — take the last snapshot of each day as the day's value
    by_date: dict[str, dict] = {}
    for r in rows:
        day = r.get("date", r.get("timestamp", "")[:10])
        by_date[day] = r  # later rows overwrite earlier ones for same day

    sorted_days = sorted(by_date.values(), key=lambda x: x.get("date", ""))
    dau_values = [int(d.get("active_today", 0)) for d in sorted_days]
    dates_seen = list(by_date.keys())

    total_users_end = int(sorted_days[-1].get("total_users", 0)) if sorted_days else 0
    total_users_start = int(sorted_days[0].get("total_users", 0)) if sorted_days else 0
    new_users = max(0, total_users_end - total_users_start)

    dau = round(sum(dau_values) / len(dau_values), 1) if dau_values else 0.0
    wau = len({d for d in dates_seen})  # days with at least one snapshot

    # Retention: active_today on last day / total_users at start (rough estimate)
    last_active = dau_values[-1] if dau_values else 0
    retention_pct = (
        round(last_active / total_users_start * 100, 1)
        if total_users_start > 0
        else 0.0
    )

    xp_values = [int(d.get("total_xp_today", 0)) for d in sorted_days]
    avg_xp = round(sum(xp_values) / len(xp_values), 1) if xp_values else 0.0

    most_active_day = ""
    if dau_values and sorted_days:
        idx = dau_values.index(max(dau_values))
        most_active_day = sorted_days[idx].get("date", "")

    avg_streak_values = [float(d.get("avg_streak", 0)) for d in sorted_days]
    avg_streak = round(sum(avg_streak_values) / len(avg_streak_values), 2) if avg_streak_values else 0.0

    return {
        "period_start": sorted_days[0].get("date", "") if sorted_days else "",
        "period_end": sorted_days[-1].get("date", "") if sorted_days else "",
        "total_users": total_users_end,
        "new_users": new_users,
        "dau": dau,
        "wau": wau,
        "retention_pct": retention_pct,
        "avg_xp_per_day": avg_xp,
        "most_active_day": most_active_day,
        "avg_streak": avg_streak,
    }


async def _generate_weekly_summary(metrics: dict) -> str:
    """Ask gpt-4o-mini to summarize the real metrics in Ukrainian."""
    prompt = (
        "Ось реальна статистика Telegram-бота ThreeWordsDaily за тиждень:\n\n"
        f"{json.dumps(metrics, ensure_ascii=False, indent=2)}\n\n"
        "Зроби коротке резюме (3–5 речень) українською мовою. "
        "Вкажи на найважливішу метрику, одну конкретну пораду для покращення, "
        "і коротку оцінку тижня. Використовуй тільки наведені дані."
    )
    try:
        resp = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ти аналітик Telegram-ботів. Коротко і по суті."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=400,
            temperature=0.4,
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        logger.error("OpenAI weekly summary failed: %s", exc)
        return "(AI-резюме недоступне — помилка OpenAI)"


async def task_weekly_report() -> None:
    """Read last 7 days of snapshots, compute metrics, generate AI summary, report."""
    logger.info("Running weekly analytics report...")

    rows = await sheets_read("content_metrics")

    # Filter to last 7 days
    cutoff = (datetime.now() - timedelta(days=7)).date().isoformat()
    recent_rows = [
        r for r in rows
        if r.get("date", r.get("timestamp", ""))[:10] >= cutoff
    ]

    if not recent_rows:
        msg = (
            "Тижневий звіт: даних за останні 7 днів не знайдено в content_metrics. "
            "Перевірте чи працює збір метрик (task_metrics_snapshot)."
        )
        logger.warning(msg)
        await send_telegram(msg)
        return

    metrics = _compute_weekly_metrics(recent_rows)
    logger.info("Weekly metrics computed: %s", metrics)

    ai_summary = await _generate_weekly_summary(metrics)

    report_text = (
        f"Тижневий звіт ThreeWordsDaily\n"
        f"Період: {metrics.get('period_start')} — {metrics.get('period_end')}\n\n"
        f"Юзерів всього: {metrics.get('total_users')}\n"
        f"Нових за тиждень: {metrics.get('new_users')}\n"
        f"DAU (середнє): {metrics.get('dau')}\n"
        f"WAU (днів з активністю): {metrics.get('wau')}\n"
        f"Retention (приблизно): {metrics.get('retention_pct')}%\n"
        f"Середній XP/день: {metrics.get('avg_xp_per_day')}\n"
        f"Найактивніший день: {metrics.get('most_active_day')}\n"
        f"Середній streak: {metrics.get('avg_streak')} днів\n\n"
        f"AI-резюме:\n{ai_summary}"
    )

    await send_telegram(report_text)

    # Save to Sheets analytics tab
    saved = await sheets_append_row(
        "analytics",
        {**metrics, "ai_summary": ai_summary, "reported_at": datetime.now().isoformat()},
    )
    if not saved:
        logger.warning("Could not save weekly report to Sheets analytics tab.")


# ======= TASK 3: SUNDAY 23:00 — WEEKLY CONTENT PLAN =======

async def _read_used_words() -> list[str]:
    """Read used_words from Sheets. Returns list of words (may be empty)."""
    rows = await sheets_read("used_words")
    words = [r.get("word", "") for r in rows if r.get("word")]
    if not words:
        logger.warning("used_words tab returned no data.")
    return words


async def _read_analytics_summary() -> str:
    """Read analytics tab and produce a short summary for the planner prompt."""
    rows = await sheets_read("analytics")
    if not rows:
        return "Немає даних аналітики."
    # Take the most recent row
    last = rows[-1]
    return (
        f"Остання аналітика ({last.get('period_start')} — {last.get('period_end')}): "
        f"DAU={last.get('dau')}, retention={last.get('retention_pct')}%, "
        f"avg_xp={last.get('avg_xp_per_day')}, "
        f"AI-резюме: {last.get('ai_summary', 'немає')}"
    )


async def _generate_content_plan(used_words: list[str], analytics_summary: str) -> list[dict]:
    """Ask gpt-4o-mini to generate a 7-day content plan as a list of day dicts."""
    next_monday = datetime.now() + timedelta(days=(7 - datetime.now().weekday()) % 7 or 7)
    week_start = next_monday.strftime("%Y-%m-%d")
    week_dates = [
        (next_monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)
    ]

    used_str = ", ".join(used_words[-50:]) if used_words else "немає даних"

    prompt = (
        f"Ось реальні дані:\n"
        f"Вже використані слова: {used_str}\n"
        f"Аналітика: {analytics_summary}\n\n"
        f"Склади контент-план на 7 днів починаючи з {week_start}.\n"
        f"Дні: {', '.join(week_dates)}\n\n"
        "Поверни JSON-масив із 7 об'єктів. Кожен об'єкт:\n"
        '{"date": "YYYY-MM-DD", "word": "english_word", "word_category": "category", '
        '"idiom": "English idiom", "story_theme": "short theme description"}\n\n'
        "Не повторювати слова зі списку використаних. Тільки JSON-масив."
    )
    try:
        resp = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ти контент-менеджер для Telegram-бота з вивчення англійської. "
                        "Відповідай тільки валідним JSON-масивом."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=1200,
            temperature=0.6,
        )
        raw = resp.choices[0].message.content.strip()
        plan_days: list[dict] = json.loads(raw)
        return plan_days
    except json.JSONDecodeError as exc:
        logger.error("Content plan JSON parse error: %s", exc)
        return []
    except Exception as exc:
        logger.error("OpenAI content plan generation failed: %s", exc)
        return []


async def task_weekly_content_plan() -> None:
    """Read used words + analytics, generate 7-day plan, store in Sheets, notify admin."""
    logger.info("Running weekly content plan generation...")

    used_words, analytics_summary = await asyncio.gather(
        _read_used_words(),
        _read_analytics_summary(),
    )

    plan_days = await _generate_content_plan(used_words, analytics_summary)

    if not plan_days:
        msg = (
            "Контент-план не згенеровано: OpenAI повернув порожній або невалідний результат. "
            "Перевірте логи."
        )
        logger.error(msg)
        await send_telegram(msg)
        return

    next_monday = datetime.now() + timedelta(days=(7 - datetime.now().weekday()) % 7 or 7)
    week_start = next_monday.strftime("%Y-%m-%d")

    # Save each day row to Sheets content_plan tab
    save_errors = 0
    for day in plan_days:
        row = {
            "week_start": week_start,
            "day": day.get("date", ""),
            "word": day.get("word", ""),
            "word_category": day.get("word_category", ""),
            "idiom": day.get("idiom", ""),
            "story_theme": day.get("story_theme", ""),
            "created_at": datetime.now().isoformat(),
        }
        ok = await sheets_append_row("content_plan", row)
        if not ok:
            save_errors += 1

    if save_errors:
        logger.warning(
            "Failed to save %d/%d day rows to content_plan tab.",
            save_errors,
            len(plan_days),
        )

    # Build admin notification
    lines = [f"Контент-план на тиждень з {week_start}:"]
    for day in plan_days:
        lines.append(
            f"\n{day.get('date')} [{day.get('word_category', '')}]"
            f"\n  Слово: {day.get('word')}"
            f"\n  Idiom: {day.get('idiom')}"
            f"\n  Тема: {day.get('story_theme')}"
        )
    if save_errors:
        lines.append(
            f"\nУвага: {save_errors} рядків не вдалося зберегти в Sheets (content_plan)."
        )
    await send_telegram("\n".join(lines))
    logger.info("Content plan done: %d days generated.", len(plan_days))


# ======= SCHEDULER =======

async def _run_at(hour: int, minute: int, weekday: int, task_fn, label: str) -> None:
    """Wait until the next occurrence of weekday+time, then run task_fn."""
    while True:
        now = datetime.now()
        days_ahead = (weekday - now.weekday()) % 7
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if days_ahead == 0 and next_run <= now:
            days_ahead = 7
        next_run += timedelta(days=days_ahead)
        wait_seconds = (next_run - now).total_seconds()
        logger.info(
            "Next %s scheduled at %s (in %.0f s)",
            label,
            next_run.strftime("%Y-%m-%d %H:%M"),
            wait_seconds,
        )
        await asyncio.sleep(wait_seconds)
        logger.info("Running scheduled task: %s", label)
        try:
            await task_fn()
        except Exception as exc:
            logger.error("Task %s raised an exception: %s", label, exc)


async def _run_every(interval_seconds: int, task_fn, label: str) -> None:
    """Run task_fn every interval_seconds, starting immediately."""
    while True:
        logger.info("Running periodic task: %s", label)
        try:
            await task_fn()
        except Exception as exc:
            logger.error("Periodic task %s raised an exception: %s", label, exc)
        await asyncio.sleep(interval_seconds)


async def main() -> None:
    logger.info("analytics_planner starting up. DB=%s", DB_PATH)

    await asyncio.gather(
        # Every 15 minutes
        _run_every(15 * 60, task_metrics_snapshot, "metrics_snapshot"),
        # Sunday (weekday=6) at 20:00
        _run_at(20, 0, 6, task_weekly_report, "weekly_report"),
        # Sunday (weekday=6) at 23:00
        _run_at(23, 0, 6, task_weekly_content_plan, "weekly_content_plan"),
    )


if __name__ == "__main__":
    asyncio.run(main())
