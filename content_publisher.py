"""
content_publisher.py — scheduled content publisher for @ThreeWordsDailyChat

Schedule (Europe/Kyiv timezone):
  13:00 daily     — Idiom of the day
  17:00 Friday    — Fun fact about English
  18:00 Sunday    — Weekly quiz (5 questions, poll format)
  19:00 daily     — Mini story (3–4 sentences using a recent English word)

Does NOT handle commands, does NOT send admin messages, does NOT duplicate
posts owned by learning_bot.py (09:00 word, 12:00 quiz, 20:00 motivation).
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Optional

import httpx
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

try:
    from content_plan_9months import get_current_week_plan, get_daily_words
    _CURRICULUM = True
except ImportError:
    _CURRICULUM = False

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BOT_TOKEN: str = (
    os.getenv("CONTENT_BOT_TOKEN")          # YourBot_test_bot — content publisher role
    or os.getenv("LEARNING_BOT_TOKEN")
    or os.getenv("TELEGRAM_BOT_TOKEN", "")
)
CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
SHEETS_API_URL: str = os.getenv("SHEETS_API_URL", "").strip()

KYIV_TZ = pytz.timezone("Europe/Kyiv")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("content_publisher")

# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------

openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ---------------------------------------------------------------------------
# Telegram helpers
# ---------------------------------------------------------------------------


async def _tg_post(endpoint: str, payload: dict) -> Optional[dict]:
    """Low-level Telegram API call. Returns response JSON or None on failure."""
    url = f"{TELEGRAM_API}/{endpoint}"
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(url, json=payload)
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram error: {data}")
    return data


async def send_message(text: str, parse_mode: str = "HTML") -> Optional[int]:
    """Send a text message. Returns message_id on success, None on failure."""
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": parse_mode,
    }
    data = await _tg_post("sendMessage", payload)
    return data["result"]["message_id"] if data else None


async def send_poll(
    question: str,
    options: list[str],
    correct_option_id: int,
    explanation: str,
) -> Optional[int]:
    """Send a quiz poll. Returns message_id on success, None on failure."""
    payload = {
        "chat_id": CHAT_ID,
        "question": question[:300],  # Telegram limit
        "options": options,
        "type": "quiz",
        "correct_option_id": correct_option_id,
        "explanation": explanation[:200],
        "is_anonymous": True,
    }
    data = await _tg_post("sendPoll", payload)
    return data["result"]["message_id"] if data else None


async def _send_with_retry(
    send_fn, *args, post_type: str = "post", **kwargs
) -> Optional[int]:
    """Call send_fn; on failure wait 30 s and retry once."""
    try:
        return await send_fn(*args, **kwargs)
    except Exception as exc:
        logger.error("[%s] Send failed: %s — retrying in 30 s", post_type, exc)
        await asyncio.sleep(30)
        try:
            return await send_fn(*args, **kwargs)
        except Exception as exc2:
            logger.error("[%s] Retry also failed: %s", post_type, exc2)
            return None


# ---------------------------------------------------------------------------
# Google Sheets logging (non-blocking)
# ---------------------------------------------------------------------------


async def log_to_sheets(
    post_type: str, content_preview: str, message_id: Optional[int]
) -> None:
    """Write a row to content_metrics sheet. Failure is logged and ignored."""
    if not SHEETS_API_URL:
        return
    payload = {
        "sheet": "content_metrics",
        "post_type": post_type,
        "content_preview": content_preview[:100],
        "posted_at": datetime.now(KYIV_TZ).isoformat(),
        "telegram_message_id": message_id,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(f"{SHEETS_API_URL}/content_metrics", json=payload)
        logger.info("[sheets] Logged %s (msg_id=%s)", post_type, message_id)
    except Exception as exc:
        logger.warning("[sheets] Could not log metrics: %s", exc)


# ---------------------------------------------------------------------------
# Content generators
# ---------------------------------------------------------------------------


async def _chat(system: str, user: str, max_tokens: int, temperature: float) -> str:
    """Thin wrapper around OpenAI chat completions."""
    resp = await openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return resp.choices[0].message.content.strip()


def _get_curriculum_context() -> dict:
    """Return current week's curriculum data, or empty dict if unavailable."""
    if not _CURRICULUM:
        return {}
    plan = get_current_week_plan()
    return plan if plan else {}


async def generate_idiom() -> str:
    """Generate the idiom-of-the-day post — uses curriculum idiom when available."""
    ctx = _get_curriculum_context()
    system = (
        "You are a friendly English teacher for Ukrainian learners at A2–B1 level. "
        "Write clearly and concisely in the exact format requested."
    )
    if ctx:
        idiom_hint = f"Use this specific idiom: '{ctx['idiom']}' which means: {ctx['idiom_meaning']}. Theme: {ctx['theme']}."
    else:
        idiom_hint = "Choose one common English idiom."

    user = (
        f"{idiom_hint}\n\n"
        "Format for Telegram (HTML):\n\n"
        "<b>Idiom of the day 💬</b>\n\n"
        "Today's idiom: <b>[idiom]</b>\n"
        "🇺🇦 [Ukrainian translation]\n\n"
        "Meaning: <i>[1–2 sentence explanation in English]</i>\n\n"
        "Example: \"[natural example sentence]\"\n"
        "<i>— [Ukrainian translation of the example]</i>\n\n"
        "Output only this format, nothing else."
    )
    return await _chat(system, user, max_tokens=300, temperature=0.8)


async def generate_fun_fact() -> str:
    """Generate a Friday fun fact about English (HTML formatted)."""
    system = (
        "You are an engaging English language enthusiast. "
        "Share genuinely surprising, little-known facts about English."
    )
    user = (
        "Give one genuinely interesting, lesser-known fact about the English language. "
        "Use this exact HTML format for Telegram:\n\n"
        "<b>Friday fun fact \U0001f92f</b>\n\n"
        "[2–3 sentences — surprising and entertaining]\n\n"
        "<i>#funfact #English</i>\n\n"
        "Output only this format, nothing else."
    )
    return await _chat(system, user, max_tokens=200, temperature=0.9)


async def generate_grammar_tip() -> str:
    """Generate a grammar tip of the day using the current week's grammar focus."""
    ctx = _get_curriculum_context()
    system = (
        "You are Лекс, a grammar teacher for Ukrainian English learners at A2-B1 level. "
        "Explain grammar rules clearly with examples."
    )
    grammar_focus = ctx.get("grammar", "a common English grammar rule") if ctx else "a common English grammar rule"
    user = (
        f"Explain this grammar topic clearly: {grammar_focus}.\n\n"
        "Format for Telegram (HTML):\n\n"
        "<b>Grammar tip of the day 📚</b>\n\n"
        "<b>[Grammar topic name]</b>\n\n"
        "<i>[2-3 sentence explanation in simple English]</i>\n\n"
        "✅ <b>Correct:</b> [example]\n"
        "❌ <b>Wrong:</b> [common mistake]\n\n"
        "🇺🇦 [Brief Ukrainian explanation — 1 sentence]\n\n"
        "Output only this format, nothing else."
    )
    return await _chat(system, user, max_tokens=300, temperature=0.6)


async def generate_mini_story() -> str:
    """Generate an evening mini story — uses curriculum story prompt when available."""
    ctx = _get_curriculum_context()
    system = (
        "You are an English teacher for Ukrainian learners at A2–B1 level. "
        "Write short, engaging stories with a clear teaching purpose."
    )
    if ctx:
        story_hint = (
            f"Write a mini story based on this prompt: {ctx['mini_story_prompt']}\n"
            f"The story should relate to this week's theme: {ctx['theme']}."
        )
    else:
        story_hint = "Write a mini story (3–4 sentences) that naturally uses one useful English vocabulary word."

    user = (
        f"{story_hint}\n\n"
        "Bold the key vocabulary word(s) using <b>word</b>. "
        "Format for Telegram (HTML):\n\n"
        "<b>Mini story of the evening 📖</b>\n\n"
        "<i>[3–4 sentence story in English, key words in <b>bold</b>]</i>\n\n"
        "🇺🇦 <i>[Ukrainian translation]</i>\n\n"
        "Word of the story: <b>[target word]</b> — [Ukrainian meaning]\n\n"
        "Output only this format, nothing else."
    )
    return await _chat(system, user, max_tokens=350, temperature=0.9)


async def generate_weekly_quiz() -> list[dict]:
    """Generate 5 quiz questions — based on curriculum words when available."""
    ctx = _get_curriculum_context()
    system = (
        "You are an English teacher creating quiz questions for Ukrainian learners "
        "at A2–B1 level. Return only valid JSON, no extra text."
    )
    if ctx and ctx.get("words"):
        words_sample = ctx["words"][:8]
        words_str = ", ".join(f"'{w['en']}' ({w['ua']})" for w in words_sample)
        topic_hint = (
            f"This week's theme is '{ctx['theme']}'. "
            f"Use some of these vocabulary words in your questions: {words_str}. "
            f"Also test the grammar: {ctx['grammar']}."
        )
    else:
        topic_hint = "Cover mixed English vocabulary and grammar topics."

    user = (
        f"{topic_hint}\n\n"
        "Create 5 multiple-choice questions. Each must have exactly 4 answer options. "
        "Return a JSON array in this exact shape:\n"
        "[\n"
        '  {\n'
        '    "question": "What does \'resilient\' mean?",\n'
        '    "answers": ["Stubborn", "Adaptable and strong", "Careless", "Excited"],\n'
        '    "correct": 1,\n'
        '    "explanation": "Resilient means able to recover quickly from difficulties."\n'
        "  }\n"
        "]\n\n"
        "Vary types: definitions, fill-in-the-blank, synonyms, grammar corrections. "
        "Only JSON, nothing else."
    )
    raw = await _chat(system, user, max_tokens=900, temperature=0.6)
    cleaned = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    return json.loads(cleaned)


# ---------------------------------------------------------------------------
# Scheduled job handlers
# ---------------------------------------------------------------------------


async def job_idiom() -> None:
    """13:00 daily — Idiom of the day."""
    logger.info("Running job: idiom_of_day")
    try:
        text = await generate_idiom()
    except Exception as exc:
        logger.error("[idiom] OpenAI failed: %s — skipping post", exc)
        return

    message_id = await _send_with_retry(send_message, text, post_type="idiom")
    if message_id:
        logger.info("[idiom] Posted successfully (msg_id=%s)", message_id)
        asyncio.ensure_future(log_to_sheets("idiom_of_day", text, message_id))
    else:
        logger.error("[idiom] Post ultimately failed, skipping metrics log")


async def job_grammar_tip() -> None:
    """16:00 daily — Grammar tip using current week's grammar focus."""
    logger.info("Running job: grammar_tip")
    try:
        text = await generate_grammar_tip()
    except Exception as exc:
        logger.error("[grammar_tip] OpenAI failed: %s — skipping post", exc)
        return
    message_id = await _send_with_retry(send_message, text, post_type="grammar_tip")
    if message_id:
        logger.info("[grammar_tip] Posted successfully (msg_id=%s)", message_id)
        asyncio.ensure_future(log_to_sheets("grammar_tip", text, message_id))
    else:
        logger.error("[grammar_tip] Post ultimately failed")


async def job_fun_fact() -> None:
    """17:00 Friday — Fun fact about English."""
    logger.info("Running job: fun_fact")
    try:
        text = await generate_fun_fact()
    except Exception as exc:
        logger.error("[fun_fact] OpenAI failed: %s — skipping post", exc)
        return

    message_id = await _send_with_retry(send_message, text, post_type="fun_fact")
    if message_id:
        logger.info("[fun_fact] Posted successfully (msg_id=%s)", message_id)
        asyncio.ensure_future(log_to_sheets("fun_fact", text, message_id))
    else:
        logger.error("[fun_fact] Post ultimately failed, skipping metrics log")


async def job_weekly_quiz() -> None:
    """18:00 Sunday — Weekly quiz (5 poll questions)."""
    logger.info("Running job: weekly_quiz")
    try:
        questions = await generate_weekly_quiz()
    except Exception as exc:
        logger.error("[weekly_quiz] OpenAI failed: %s — skipping post", exc)
        return

    # Intro message
    intro = (
        "<b>Weekly Quiz \U0001f3c6</b>\n\n"
        "Test your English knowledge! Five questions coming up \U0001f447"
    )
    intro_id = await _send_with_retry(send_message, intro, post_type="weekly_quiz_intro")
    if intro_id is None:
        logger.error("[weekly_quiz] Could not send intro — aborting quiz")
        return

    await asyncio.sleep(2)

    last_message_id: Optional[int] = intro_id
    for idx, q in enumerate(questions, start=1):
        question_text = f"{idx}/5 — {q['question']}"
        try:
            msg_id = await _send_with_retry(
                send_poll,
                question_text,
                q["answers"],
                q["correct"],
                q.get("explanation", ""),
                post_type=f"weekly_quiz_q{idx}",
            )
            if msg_id:
                last_message_id = msg_id
                logger.info("[weekly_quiz] Poll %d/5 sent (msg_id=%s)", idx, msg_id)
            else:
                logger.error("[weekly_quiz] Poll %d/5 failed to send", idx)
        except Exception as exc:
            logger.error("[weekly_quiz] Poll %d/5 error: %s", idx, exc)

        if idx < len(questions):
            await asyncio.sleep(3)

    asyncio.ensure_future(
        log_to_sheets("weekly_quiz", intro, last_message_id)
    )


async def job_mini_story() -> None:
    """19:00 daily — Mini story."""
    logger.info("Running job: mini_story")
    try:
        text = await generate_mini_story()
    except Exception as exc:
        logger.error("[mini_story] OpenAI failed: %s — skipping post", exc)
        return

    message_id = await _send_with_retry(send_message, text, post_type="mini_story")
    if message_id:
        logger.info("[mini_story] Posted successfully (msg_id=%s)", message_id)
        asyncio.ensure_future(log_to_sheets("mini_story", text, message_id))
    else:
        logger.error("[mini_story] Post ultimately failed, skipping metrics log")


# ---------------------------------------------------------------------------
# Scheduler setup
# ---------------------------------------------------------------------------


def build_scheduler() -> AsyncIOScheduler:
    """Create and configure the AsyncIOScheduler with all content jobs."""
    scheduler = AsyncIOScheduler(timezone=KYIV_TZ)

    # 13:00 every day — idiom
    scheduler.add_job(
        job_idiom,
        trigger="cron",
        hour=13,
        minute=0,
        id="idiom_of_day",
        name="Idiom of the day",
        misfire_grace_time=300,
    )

    # 16:00 every day — grammar tip (from curriculum)
    scheduler.add_job(
        job_grammar_tip,
        trigger="cron",
        hour=16,
        minute=0,
        id="grammar_tip",
        name="Grammar tip of the day",
        misfire_grace_time=300,
    )

    # 17:00 every Friday (day_of_week=4) — fun fact
    scheduler.add_job(
        job_fun_fact,
        trigger="cron",
        day_of_week=4,
        hour=17,
        minute=0,
        id="fun_fact_friday",
        name="Friday fun fact",
        misfire_grace_time=300,
    )

    # 18:00 every Sunday (day_of_week=6) — weekly quiz
    scheduler.add_job(
        job_weekly_quiz,
        trigger="cron",
        day_of_week=6,
        hour=18,
        minute=0,
        id="weekly_quiz_sunday",
        name="Sunday weekly quiz",
        misfire_grace_time=300,
    )

    # 19:00 every day — mini story
    scheduler.add_job(
        job_mini_story,
        trigger="cron",
        hour=19,
        minute=0,
        id="mini_story",
        name="Mini story of the evening",
        misfire_grace_time=300,
    )

    return scheduler


# ---------------------------------------------------------------------------
# Startup validation
# ---------------------------------------------------------------------------


def _validate_config() -> None:
    missing = []
    if not BOT_TOKEN:
        missing.append("LEARNING_BOT_TOKEN (or TELEGRAM_BOT_TOKEN)")
    if not CHAT_ID:
        missing.append("TELEGRAM_CHAT_ID")
    if not OPENAI_API_KEY:
        missing.append("OPENAI_API_KEY")
    if missing:
        raise EnvironmentError(
            "Missing required environment variables: " + ", ".join(missing)
        )
    if not SHEETS_API_URL:
        logger.warning("SHEETS_API_URL is not set — Sheets logging will be skipped")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def main() -> None:
    _validate_config()

    scheduler = build_scheduler()
    scheduler.start()

    now_kyiv = datetime.now(KYIV_TZ).strftime("%Y-%m-%d %H:%M:%S %Z")
    logger.info("content_publisher started — current Kyiv time: %s", now_kyiv)

    jobs = scheduler.get_jobs()
    for job in jobs:
        next_run = job.next_run_time.strftime("%Y-%m-%d %H:%M %Z") if job.next_run_time else "N/A"
        logger.info("  Scheduled: %-30s  next run: %s", job.name, next_run)

    try:
        # Keep the event loop alive indefinitely
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown signal received — stopping scheduler")
    finally:
        scheduler.shutdown(wait=False)
        logger.info("content_publisher stopped")


if __name__ == "__main__":
    asyncio.run(main())
