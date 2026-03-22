"""
agents/reengagement_agent.py — Voodoo Smart Re-engagement System

Segments inactive users and sends personalized notifications to bring them back.
Runs daily at 11:00 Kyiv time (called from autonomous_loop.py).

Segments:
  1 day   — gentle reminder (lesson waiting)
  2 days  — streak warning (серія під загрозою)
  3-6 days — pet sad message (pet-based emotional nudge)
  7-14 days — comeback offer (+2x XP for today)
  15-60 days — win-back (friendly re-intro)

Anti-spam: tracks sends in nudge_log table, 23h cooldown per user.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("reengagement")
logging.basicConfig(
    format="%(asctime)s [reengagement] %(levelname)s %(message)s",
    level=logging.INFO,
)

BOT_TOKEN = os.getenv("VOODOO_BOT_TOKEN", "")        # main @v00dooBot for DMs
OPS_TOKEN = os.getenv("VOODOO_OPS_BOT_TOKEN", "")
ADMIN_ID  = int(os.getenv("ADMIN_CHAT_ID", "0"))
DB_PATH   = Path(os.getenv("DB_PATH", Path(__file__).parent.parent / "database" / "voodoo.db"))

MINIAPP_URL = os.getenv("MINIAPP_URL", "https://t.me/v00dooBot/app")

# Max sends per segment per day (anti-flood)
SEGMENT_LIMITS = {
    "gentle":   500,
    "warning":  300,
    "pet_sad":  200,
    "comeback": 100,
    "winback":  50,
}

# ── Message templates ──────────────────────────────────────────────────────────

TEMPLATES = {
    "gentle": [
        "👋 {name}! Сьогодні є нове слово дня в Voodoo English.\n\n"
        "Зайди на 2 хвилини — і серія продовжується! 🔥",
        "📚 {name}, твій урок чекає!\n\n"
        "Всього 3 слова сьогодні — і +30 XP в кишені 🎯",
        "🦊 {pet} скучив за тобою, {name}!\n\n"
        "Зайди в Voodoo — пройди урок і нагодуй свого пета 🍎",
    ],
    "warning": [
        "⚠️ {name}, твоя серія 🔥{streak} під загрозою!\n\n"
        "Ще один день без уроку — і все з нуля.\n"
        "У тебе є {freeze} заморозок — використай одну або пройди урок прямо зараз!",
        "🚨 {name}! Серія {streak} днів може зламатись!\n\n"
        "{pet} дивиться на тебе з надією...\n"
        "Один урок = серія врятована 🛡️",
        "⏰ {name}, це нагадування від {pet}:\n\n"
        "Твоя 🔥{streak}-денна серія закінчується сьогодні!\n"
        "Заходь і збережи прогрес → @v00dooBot",
    ],
    "pet_sad": [
        "😢 {pet} дуже сумує...\n\n"
        "{name}, ти не заходив {days} днів. {pet} хоч і сумний, але вірить у тебе!\n\n"
        "Поверни посмішку своєму пету → один урок сьогодні 📚",
        "🥺 {name}! {pet} залишився сам...\n\n"
        "Вже {days} днів без тебе. Твій пет не їсть, не грає...\n"
        "Нагодуй {pet} новими словами! 🍎",
        "💔 {pet} написав листа:\n\n"
        "«{name}, де ти? Я чекаю на тебе вже {days} дні.\n"
        "Повернись, будь ласка, і давай вчитись разом!»\n\n"
        "→ @v00dooBot",
    ],
    "comeback": [
        "🌟 {name}! Ти пропустив {days} днів, але ніколи не пізно повернутись!\n\n"
        "Спеціально для тебе: сьогодні <b>2x XP</b> за перший урок після паузи 🚀\n\n"
        "Жми → @v00dooBot і починай!",
        "🎯 {name}, довга пауза — це не кінець.\n\n"
        "Поверни свою серію:\n"
        "→ Пройди 1 урок сьогодні\n"
        "→ Отримай 2x XP як comeback bonus\n"
        "→ {pet} радітиме!\n\n"
        "Старт: @v00dooBot",
        "💫 {name}! Тисячі людей вчаться з Voodoo прямо зараз.\n\n"
        "Ти теж можеш повернутись — {days} днів паузи не рахуються!\n"
        "Comeback bonus: +50 XP за перший урок сьогодні 🎁",
    ],
    "winback": [
        "👋 {name}! Давно не бачились.\n\n"
        "Voodoo English весь час оновлюється:\n"
        "• 12 нових ігор\n"
        "• Система рівнів і ліг\n"
        "• Твій пет {pet} ще живий і чекає!\n\n"
        "Повернись: @v00dooBot",
        "🪄 {name}, у Voodoo є нові фічі, які ти ще не бачив!\n\n"
        "→ Liга Bronze/Silver/Gold/Diamond\n"
        "→ 12 міні-ігор\n"
        "→ Підкаст на твоєму рівні\n"
        "→ Telegram Stars монетизація\n\n"
        "Хочеш побачити? → @v00dooBot",
    ],
}


def _get_segment(days_inactive: int) -> str | None:
    if days_inactive == 1:
        return "gentle"
    elif days_inactive == 2:
        return "warning"
    elif 3 <= days_inactive <= 6:
        return "pet_sad"
    elif 7 <= days_inactive <= 14:
        return "comeback"
    elif 15 <= days_inactive <= 60:
        return "winback"
    return None


async def _send_dm(tg_id: int, text: str) -> bool:
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": tg_id,
                    "text": text,
                    "parse_mode": "HTML",
                },
            )
            return r.json().get("ok", False)
    except Exception:
        return False


def _was_nudged_recently(conn: sqlite3.Connection, tg_id: int, hours: int = 22) -> bool:
    try:
        row = conn.execute(
            "SELECT sent_at FROM nudge_log WHERE tg_id=? ORDER BY sent_at DESC LIMIT 1",
            (tg_id,),
        ).fetchone()
        if not row:
            return False
        last = datetime.fromisoformat(str(row[0]).replace("Z", ""))
        return (datetime.utcnow() - last).total_seconds() < hours * 3600
    except Exception:
        return False


def _log_nudge(conn: sqlite3.Connection, tg_id: int, segment: str) -> None:
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS nudge_log (tg_id INTEGER, segment TEXT DEFAULT '', sent_at TEXT)"
        )
        conn.execute(
            "INSERT INTO nudge_log (tg_id, segment, sent_at) VALUES (?, ?, datetime('now'))",
            (tg_id, segment),
        )
        conn.commit()
    except Exception as e:
        log.debug("nudge_log write error: %s", e)


async def run_reengagement() -> dict:
    """Main re-engagement cycle. Returns stats dict."""
    if not BOT_TOKEN:
        log.error("VOODOO_BOT_TOKEN not set — cannot send DMs")
        return {}
    if not DB_PATH.exists():
        log.warning("DB not found at %s", DB_PATH)
        return {}

    now = datetime.utcnow()
    stats = {seg: 0 for seg in SEGMENT_LIMITS}
    stats["skipped"] = 0
    stats["errors"]  = 0

    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row

    try:
        # Get users with last_lesson_date set (they've done at least one lesson)
        rows = conn.execute(
            """SELECT tg_id, first_name, pet_name, pet_character, streak,
                      streak_freeze, last_lesson_date, last_active
               FROM users
               WHERE last_lesson_date != '' AND last_lesson_date IS NOT NULL
               ORDER BY last_lesson_date DESC
               LIMIT 5000"""
        ).fetchall()

        for row in rows:
            tg_id   = row["tg_id"]
            fname   = row["first_name"] or "друже"
            pet     = row["pet_name"] or row["pet_character"] or "Лексик"
            streak  = row["streak"] or 0
            freeze  = row["streak_freeze"] or 0
            last    = row["last_lesson_date"] or ""

            try:
                last_date = datetime.strptime(last[:10], "%Y-%m-%d")
                days_inactive = (now - last_date).days
            except Exception:
                continue

            segment = _get_segment(days_inactive)
            if not segment:
                continue

            # Check segment limit for today
            if stats.get(segment, 0) >= SEGMENT_LIMITS.get(segment, 999):
                continue

            # Skip if nudged recently
            if _was_nudged_recently(conn, tg_id):
                stats["skipped"] += 1
                continue

            # Pick template
            tmpl = random.choice(TEMPLATES[segment])
            text = tmpl.format(
                name=fname,
                pet=pet,
                streak=streak,
                freeze=freeze,
                days=days_inactive,
            )

            ok = await _send_dm(tg_id, text)
            if ok:
                _log_nudge(conn, tg_id, segment)
                stats[segment] = stats.get(segment, 0) + 1
                log.info("Nudged %d [%s] (%d days inactive)", tg_id, segment, days_inactive)
            else:
                stats["errors"] += 1

            await asyncio.sleep(0.08)  # ~12 msgs/sec, safe rate

    finally:
        conn.close()

    return stats


async def ops_report(text: str) -> None:
    if not OPS_TOKEN or not ADMIN_ID:
        return
    import httpx
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            await c.post(
                f"https://api.telegram.org/bot{OPS_TOKEN}/sendMessage",
                json={"chat_id": ADMIN_ID, "text": text, "parse_mode": "HTML"},
            )
    except Exception:
        pass


async def main() -> None:
    log.info("Re-engagement agent starting...")
    stats = await run_reengagement()
    total = sum(v for k, v in stats.items() if k not in ("skipped", "errors"))
    report = (
        f"📬 <b>Re-engagement cycle complete</b>\n\n"
        f"✅ Gentle:   {stats.get('gentle', 0)}\n"
        f"⚠️ Warning:  {stats.get('warning', 0)}\n"
        f"😢 Pet sad:  {stats.get('pet_sad', 0)}\n"
        f"🌟 Comeback: {stats.get('comeback', 0)}\n"
        f"👋 Winback:  {stats.get('winback', 0)}\n\n"
        f"<b>Total sent: {total}</b>\n"
        f"Skipped: {stats.get('skipped', 0)} | Errors: {stats.get('errors', 0)}"
    )
    log.info(report.replace("<b>", "").replace("</b>", ""))
    await ops_report(report)


if __name__ == "__main__":
    asyncio.run(main())
