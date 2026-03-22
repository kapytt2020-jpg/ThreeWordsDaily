"""
agents/podcast_agent.py — Voodoo Podcast Generation System

Generates Ukrainian-language audio podcasts about English learning.
Pipeline:
  1. GPT-4o   → Ukrainian script (3-5 min, personalized or general)
  2. OpenAI TTS → MP3 audio file
  3. Bot API  → Send voice message to user or group topic

Modes:
  - personal(tg_id)  → personalized podcast using user's recent words
  - weekly()         → general weekly episode for the group channel
  - group_topic()    → post to forum topic in internal group
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger("voodoo.podcast")

OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY", "")
BOT_TOKEN       = os.getenv("VOODOO_BOT_TOKEN", "")
GROUP_ID        = os.getenv("INTERNAL_GROUP_ID", "")
TG_API         = "https://api.telegram.org"

# Forum topic ID for 📻 Podcast topic — update if different
PODCAST_TOPIC_ID = int(os.getenv("PODCAST_TOPIC_ID", "76"))


# ── Script generation ──────────────────────────────────────────────────────────

PODCAST_SYSTEM = """Ти — ведучий подкасту "Voodoo English" для україномовних студентів.
Стиль: живий, природній, як розмова з другом. Не занадто офіційно.
Формат скрипту: тільки текст для читання вголос (без ремарок у дужках, без HTML).
Мова подкасту: українська. Англійські слова вимовляй разом з транскрипцією.
Довжина: приблизно 400-600 слів (3-4 хвилини аудіо).
Завжди закінчуй заохоченням вчитися далі і нагадуванням відкрити Voodoo бот."""


async def generate_personal_script(words: list[dict], user_name: str = "друже") -> str:
    """Generate personalized podcast script based on user's recent words."""
    from agents.base import _anthropic_call

    word_list = "\n".join(
        f"- {w.get('word','?')} [{w.get('ipa','')}] — {w.get('translation','?')} "
        f"(приклад: {w.get('example_en','')})"
        for w in words[:7]
    )

    prompt = f"""Створи епізод подкасту "Voodoo English" для учня на ім'я {user_name}.

Слова які він/вона нещодавно вивчав/вивчала:
{word_list}

Структура епізоду:
1. Привітання (звернись до {user_name} особисто, 2-3 речення)
2. Короткий огляд: про що сьогоднішній епізод
3. Для кожного слова (вибери 3-5 найцікавіших):
   - Вимов слово і перекладі
   - Поясни значення простими словами
   - Наведи живий приклад з реального життя
   - Один life hack щоб запам'ятати
4. Коротка вправа для слухача (мисленнєва)
5. Заохочення і пращання

Пиши тільки текст для читання вголос."""

    return await _anthropic_call(PODCAST_SYSTEM, prompt, max_tokens=1200)


async def generate_weekly_script(theme: str = "") -> str:
    """Generate weekly general podcast episode."""
    from agents.base import _anthropic_call

    today = date.today()
    week_num = today.isocalendar()[1]

    if not theme:
        themes = [
            "слова для роботи та кар'єри", "емоції та почуття",
            "подорожі та туризм", "технології та гаджети",
            "їжа та ресторани", "спорт та активний відпочинок",
            "мистецтво та культура", "природа та екологія",
        ]
        theme = themes[week_num % len(themes)]

    prompt = f"""Створи тижневий епізод подкасту "Voodoo English", тиждень {week_num}.

Тема епізоду: {theme}

Структура:
1. Привітання всіх слухачів (загальне, тепле)
2. Анонс теми тижня
3. 5 ключових слів за темою "{theme}":
   - Слово + вимова + переклад
   - Визначення своїми словами
   - Реальний приклад використання
   - Порада як запам'ятати
4. Міні-діалог: покажи як ці слова звучать в розмові
5. Виклик тижня: щодня використовувати 1 нове слово
6. Нагадування: заходь в @VoodooEnglishBot щоб практикувати

Тільки текст для читання вголос, природня мова."""

    return await _anthropic_call(PODCAST_SYSTEM, prompt, max_tokens=1400)


# ── Audio generation via OpenAI TTS ───────────────────────────────────────────

async def text_to_speech(
    text: str,
    voice: str = "nova",          # nova = female, warm tone; onyx = male, deep
    model: str = "tts-1",         # tts-1 (fast) or tts-1-hd (higher quality)
    output_path: Optional[Path] = None,
) -> Path:
    """Convert text to MP3 using OpenAI TTS. Returns path to audio file."""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set")

    if output_path is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        output_path = Path(tmp.name)
        tmp.close()

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "input": text,
        "voice": voice,
        "response_format": "mp3",
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            "https://api.openai.com/v1/audio/speech",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        output_path.write_bytes(resp.content)

    log.info("TTS generated: %s (%.1f KB)", output_path, output_path.stat().st_size / 1024)
    return output_path


# ── Telegram delivery ──────────────────────────────────────────────────────────

async def send_voice_to_user(
    tg_id: int,
    audio_path: Path,
    caption: str = "",
) -> bool:
    """Send voice/audio message to a single user."""
    url = f"{TG_API}/bot{BOT_TOKEN}/sendAudio"

    async with httpx.AsyncClient(timeout=60) as client:
        with open(audio_path, "rb") as f:
            data = {"chat_id": tg_id}
            if caption:
                data["caption"] = caption
                data["parse_mode"] = "HTML"
            resp = await client.post(url, data=data, files={"audio": f})

    if resp.status_code == 200:
        log.info("Podcast sent to user %s", tg_id)
        return True
    else:
        log.error("Failed to send to %s: %s", tg_id, resp.text[:200])
        return False


async def send_voice_to_topic(
    audio_path: Path,
    thread_id: int,
    caption: str = "",
) -> bool:
    """Send audio to forum topic in internal group."""
    url = f"{TG_API}/bot{BOT_TOKEN}/sendAudio"

    async with httpx.AsyncClient(timeout=60) as client:
        with open(audio_path, "rb") as f:
            data = {
                "chat_id": GROUP_ID,
                "message_thread_id": thread_id,
            }
            if caption:
                data["caption"] = caption
                data["parse_mode"] = "HTML"
            resp = await client.post(url, data=data, files={"audio": f})

    ok = resp.status_code == 200
    if ok:
        log.info("Podcast sent to group topic %s", thread_id)
    else:
        log.error("Failed to send to group topic: %s", resp.text[:200])
    return ok


# ── High-level pipeline functions ─────────────────────────────────────────────

async def generate_and_send_personal(tg_id: int) -> bool:
    """Full personal podcast pipeline for one user."""
    try:
        from database import db

        user = await db.get_user(tg_id)
        name = user.get("first_name", "друже") or "друже"

        # Get user's recently learned words
        words = await _get_user_recent_words(tg_id, limit=7)

        if not words:
            # Fallback: generic beginner episode
            words = [
                {"word": "resilient", "ipa": "/rɪˈzɪliənt/", "translation": "стійкий",
                 "example_en": "She is incredibly resilient."},
                {"word": "ambitious", "ipa": "/æmˈbɪʃəs/", "translation": "амбітний",
                 "example_en": "He is very ambitious about his career."},
                {"word": "grateful", "ipa": "/ˈɡreɪtfəl/", "translation": "вдячний",
                 "example_en": "I'm grateful for your help."},
            ]

        log.info("Generating personal podcast for user %s (%s words)", tg_id, len(words))
        script = await generate_personal_script(words, user_name=name)

        audio_path = await text_to_speech(script, voice="nova")

        today_str = date.today().strftime("%d.%m.%Y")
        caption = (
            f"🎙 <b>Твій персональний подкаст — {today_str}</b>\n\n"
            f"Voodoo English · Персональний урок\n"
            f"Слова: {', '.join(w.get('word','') for w in words[:3])}..."
        )

        success = await send_voice_to_user(tg_id, audio_path, caption)
        audio_path.unlink(missing_ok=True)
        return success

    except Exception as e:
        log.error("Personal podcast failed for %s: %s", tg_id, e)
        return False


async def generate_and_send_weekly(post_to_group: bool = True, theme: str = "") -> bool:
    """Weekly podcast — generate and post to group topic."""
    try:
        log.info("Generating weekly podcast (theme=%s)", theme or "auto")
        script = await generate_weekly_script(theme=theme)
        audio_path = await text_to_speech(script, voice="nova", model="tts-1-hd")

        week = date.today().isocalendar()[1]
        today_str = date.today().strftime("%d.%m.%Y")
        caption = (
            f"🎙 <b>Voodoo English Podcast — Тиждень {week}</b>\n\n"
            f"{today_str} · Щотижневий випуск\n"
            f"Відкрий @VoodooEnglishBot щоб практикувати ці слова"
        )

        if post_to_group:
            success = await send_voice_to_topic(audio_path, PODCAST_TOPIC_ID, caption)
        else:
            log.info("Weekly podcast generated (not sent — post_to_group=False)")
            success = True

        audio_path.unlink(missing_ok=True)
        return success

    except Exception as e:
        log.error("Weekly podcast failed: %s", e)
        return False


async def broadcast_podcast_to_all_users(theme: str = "") -> dict:
    """
    Generate one podcast episode and send to ALL active users.
    Throttled to avoid hitting Telegram limits (30 msgs/sec).
    """
    from database import db
    import sqlite3
    from pathlib import Path as P

    db_path = P(os.getenv("DB_PATH", "/Users/usernew/Desktop/VoodooBot/database/voodoo.db"))

    # Get all users who were active in last 30 days
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    from datetime import timedelta
    cutoff = str(date.today() - timedelta(days=30))
    rows = conn.execute(
        "SELECT tg_id, first_name FROM users WHERE last_active >= ?", (cutoff,)
    ).fetchall()
    conn.close()

    if not rows:
        log.info("No active users found for broadcast")
        return {"sent": 0, "failed": 0, "total": 0}

    log.info("Generating broadcast podcast for %s users", len(rows))
    script = await generate_weekly_script(theme=theme)
    audio_path = await text_to_speech(script, voice="nova", model="tts-1-hd")

    week = date.today().isocalendar()[1]
    today_str = date.today().strftime("%d.%m.%Y")
    caption = (
        f"🎙 <b>Voodoo English Podcast — Тиждень {week}</b>\n\n"
        f"{today_str} · Щотижневий випуск\n"
        f"Відкрий @VoodooEnglishBot щоб практикувати ці слова!"
    )

    sent = 0
    failed = 0
    for i, row in enumerate(rows):
        try:
            ok = await send_voice_to_user(row["tg_id"], audio_path, caption)
            if ok:
                sent += 1
            else:
                failed += 1
        except Exception as e:
            log.warning("Failed for user %s: %s", row["tg_id"], e)
            failed += 1

        # Throttle: max ~20 msgs/sec
        if i % 20 == 0 and i > 0:
            await asyncio.sleep(1)

    audio_path.unlink(missing_ok=True)
    log.info("Broadcast done: %s sent, %s failed", sent, failed)
    return {"sent": sent, "failed": failed, "total": len(rows)}


# ── DB helper ──────────────────────────────────────────────────────────────────

async def _get_user_recent_words(tg_id: int, limit: int = 7) -> list[dict]:
    """Get user's most recently seen words from DB."""
    import sqlite3
    from pathlib import Path as P

    db_path = P(os.getenv("DB_PATH", "/Users/usernew/Desktop/VoodooBot/database/voodoo.db"))
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT w.word, w.translation, w.ipa, w.example_en
               FROM user_words uw
               JOIN words w ON uw.word_id = w.id
               WHERE uw.tg_id = ?
               ORDER BY uw.last_seen DESC
               LIMIT ?""",
            (tg_id, limit)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        log.warning("Could not fetch user words: %s", e)
        return []


# ── CLI entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    logging.basicConfig(
        format="%(asctime)s [podcast] %(levelname)s %(message)s",
        level=logging.INFO,
    )

    mode = sys.argv[1] if len(sys.argv) > 1 else "weekly"

    if mode == "weekly":
        result = asyncio.run(generate_and_send_weekly(post_to_group=True))
        print(f"Weekly podcast: {'OK' if result else 'FAILED'}")

    elif mode == "user" and len(sys.argv) > 2:
        uid = int(sys.argv[2])
        result = asyncio.run(generate_and_send_personal(uid))
        print(f"Personal podcast for {uid}: {'OK' if result else 'FAILED'}")

    elif mode == "broadcast":
        theme = sys.argv[2] if len(sys.argv) > 2 else ""
        result = asyncio.run(broadcast_podcast_to_all_users(theme=theme))
        print(f"Broadcast: {result}")

    elif mode == "script":
        # Just print the script without sending
        script = asyncio.run(generate_weekly_script())
        print("\n" + "="*60)
        print(script)
        print("="*60)

    else:
        print("Usage: python -m agents.podcast_agent [weekly|user <tg_id>|broadcast|script]")
