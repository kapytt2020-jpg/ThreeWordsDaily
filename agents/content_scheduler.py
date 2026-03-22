"""
agents/content_scheduler.py — Voodoo Daily Content Scheduler

Posts daily English learning content to the Voodoo internal Telegram group.

Schedule (Kyiv time, UTC+2/UTC+3):
  09:00 — Word of the Day        → 📚 Teaching  (thread 71)
  13:00 — Fun English Fact       → 📢 Content   (thread 68)
  18:00 — Mini Quiz (Poll)       → 🧪 Testing   (thread 73)
  21:00 — Motivation Quote       → 📚 Teaching  (thread 71)

Run standalone:
  python3 agents/content_scheduler.py           # starts scheduler loop
  python3 agents/content_scheduler.py --now     # fire all posts immediately (test)
  python3 agents/content_scheduler.py --word    # post only word of the day now
  python3 agents/content_scheduler.py --fact    # post only fun fact now
  python3 agents/content_scheduler.py --quiz    # post only quiz now
  python3 agents/content_scheduler.py --motive  # post only motivation now
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import sqlite3
import sys
from datetime import datetime, date
from pathlib import Path
from zoneinfo import ZoneInfo

import aiohttp
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format="%(asctime)s [content_scheduler] %(levelname)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("content_scheduler")

# ── Config ─────────────────────────────────────────────────────────────────────

BOT_TOKEN        = os.getenv("VOODOO_OPS_BOT_TOKEN", "")
INTERNAL_GROUP_ID = int(os.getenv("INTERNAL_GROUP_ID", "0"))
DB_PATH          = Path(os.getenv("DB_PATH", Path(__file__).parent.parent / "database" / "voodoo.db"))
STATE_FILE       = Path(__file__).parent.parent / "group_state.json"
CONTENT_STATE    = Path(__file__).parent.parent / "content_state.json"
API_BASE         = f"https://api.telegram.org/bot{BOT_TOKEN}"
KYIV_TZ          = ZoneInfo("Europe/Kyiv")

# Topic thread IDs (loaded from group_state.json, with hardcoded fallbacks)
TOPIC_TEACHING   = 71
TOPIC_CONTENT    = 68
TOPIC_TESTING    = 73
TOPIC_OPS        = 70


def _load_topic_ids() -> dict:
    """Load topic_ids from group_state.json."""
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text())
            return data.get("topic_ids", {})
        except Exception:
            pass
    return {}


def _get_thread_id(topic_name: str, fallback: int) -> int:
    """Get thread ID for a topic name, with fallback."""
    topic_ids = _load_topic_ids()
    return topic_ids.get(topic_name, fallback)


# ── Content state (deduplication) ─────────────────────────────────────────────

def _load_content_state() -> dict:
    if CONTENT_STATE.exists():
        try:
            return json.loads(CONTENT_STATE.read_text())
        except Exception:
            pass
    return {}


def _save_content_state(state: dict) -> None:
    CONTENT_STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def _already_posted(content_type: str) -> bool:
    """Check if this content type was already posted today."""
    state = _load_content_state()
    today = str(date.today())
    daily = state.get("posted", {})
    return daily.get(today, {}).get(content_type, False)


def _mark_posted(content_type: str) -> None:
    """Mark a content type as posted today."""
    state = _load_content_state()
    today = str(date.today())
    if "posted" not in state:
        state["posted"] = {}
    if today not in state["posted"]:
        # Purge old dates (keep only last 7 days)
        state["posted"] = {k: v for k, v in state["posted"].items()
                           if k >= str(date.fromordinal(date.today().toordinal() - 7))}
        state["posted"][today] = {}
    state["posted"][today][content_type] = True
    _save_content_state(state)


# ── Telegram API helpers ───────────────────────────────────────────────────────

async def _tg_post(
    session: aiohttp.ClientSession,
    method: str,
    **params,
) -> dict:
    """Call a Telegram Bot API method."""
    url = f"{API_BASE}/{method}"
    try:
        async with session.post(url, json=params, timeout=aiohttp.ClientTimeout(total=15)) as r:
            data = await r.json()
            if not data.get("ok"):
                log.error("Telegram error [%s]: %s", method, data.get("description"))
            return data
    except Exception as exc:
        log.error("Telegram request failed [%s]: %s", method, exc)
        return {"ok": False}


async def send_message(
    session: aiohttp.ClientSession,
    thread_id: int,
    text: str,
    parse_mode: str = "HTML",
) -> bool:
    r = await _tg_post(
        session,
        "sendMessage",
        chat_id=INTERNAL_GROUP_ID,
        message_thread_id=thread_id,
        text=text[:4096],
        parse_mode=parse_mode,
    )
    return r.get("ok", False)


async def send_poll(
    session: aiohttp.ClientSession,
    thread_id: int,
    question: str,
    options: list[str],
    correct_option_id: int,
    explanation: str = "",
) -> bool:
    r = await _tg_post(
        session,
        "sendPoll",
        chat_id=INTERNAL_GROUP_ID,
        message_thread_id=thread_id,
        question=question[:300],
        options=options,
        type="quiz",
        correct_option_id=correct_option_id,
        explanation=explanation[:200] if explanation else "",
        is_anonymous=True,
        open_period=3600,  # 1 hour to answer
    )
    return r.get("ok", False)


# ── DB helpers ─────────────────────────────────────────────────────────────────

def _get_random_word() -> dict | None:
    """Pick a random word from the DB that hasn't been used today."""
    if not DB_PATH.exists():
        return None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        today = str(date.today())

        # Try to avoid words used in last 30 days via content_state
        state = _load_content_state()
        used_ids = state.get("used_word_ids", [])

        if used_ids:
            placeholders = ",".join("?" * len(used_ids))
            row = conn.execute(
                f"SELECT * FROM words WHERE id NOT IN ({placeholders}) "
                f"ORDER BY RANDOM() LIMIT 1",
                used_ids,
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM words ORDER BY RANDOM() LIMIT 1"
            ).fetchone()

        if row is None:
            # Fallback: pick any word
            row = conn.execute("SELECT * FROM words ORDER BY RANDOM() LIMIT 1").fetchone()

        conn.close()
        if row:
            result = dict(row)
            # Track used word ID
            state["used_word_ids"] = (used_ids + [result["id"]])[-100:]  # keep last 100
            _save_content_state(state)
            return result
    except Exception as exc:
        log.error("DB error getting word: %s", exc)
    return None


# ── Content generators ─────────────────────────────────────────────────────────

LEVEL_BADGES = {
    "A1": "🟢 A1 Beginner",
    "A2": "🟡 A2 Elementary",
    "B1": "🟠 B1 Intermediate",
    "B2": "🔵 B2 Upper-Intermediate",
    "C1": "🟣 C1 Advanced",
    "C2": "⭐ C2 Mastery",
}

WORD_EMOJIS = ["📖", "✨", "🔤", "💡", "🌟", "📝", "🗣️", "🎯"]

FALLBACK_WORDS = [
    {
        "word": "serendipity",
        "translation": "щасливий випадок, удача",
        "ipa": "/ˌser.ənˈdɪp.ɪ.ti/",
        "level": "C1",
        "example_en": "Finding my best friend was pure serendipity — we sat next to each other by chance.",
        "example_ua": "Зустріти свого найкращого друга — це було чисте щастя випадку.",
    },
    {
        "word": "resilience",
        "translation": "стійкість, здатність відновлюватися",
        "ipa": "/rɪˈzɪl.i.əns/",
        "level": "B2",
        "example_en": "Her resilience after the setback inspired everyone around her.",
        "example_ua": "Її стійкість після невдачі надихнула всіх навколо.",
    },
    {
        "word": "eloquent",
        "translation": "красномовний, виразний",
        "ipa": "/ˈel.ə.kwənt/",
        "level": "C1",
        "example_en": "He gave an eloquent speech that moved the entire audience.",
        "example_ua": "Він виголосив красномовну промову, яка зворушила всю аудиторію.",
    },
    {
        "word": "perseverance",
        "translation": "наполегливість, завзятість",
        "ipa": "/ˌpɜː.sɪˈvɪər.əns/",
        "level": "B2",
        "example_en": "Perseverance is the key to mastering any language.",
        "example_ua": "Наполегливість — ключ до оволодіння будь-якою мовою.",
    },
    {
        "word": "ephemeral",
        "translation": "короткочасний, миттєвий",
        "ipa": "/ɪˈfem.ər.əl/",
        "level": "C1",
        "example_en": "Social media fame is often ephemeral — here today, gone tomorrow.",
        "example_ua": "Слава в соцмережах часто короткочасна — сьогодні є, завтра немає.",
    },
]

FUN_FACTS = [
    ("🔤", "The word <b>\"alphabet\"</b> comes from the first two Greek letters — <i>alpha</i> (α) and <i>beta</i> (β). So every time you say \"alphabet\", you're saying the beginning of the Greek alphabet!"),
    ("🌍", "English has borrowed words from over <b>350 languages</b>! That's why we have <i>pizza</i> (Italian), <i>kindergarten</i> (German), <i>tsunami</i> (Japanese), and <i>shampoo</i> (Hindi) all in the same language."),
    ("🐌", "The word <b>\"snail mail\"</b> only appeared after email was invented in the 1990s. Before that, there was just... mail. Language adapts to technology fast!"),
    ("📚", "Shakespeare <b>invented over 1,700 words</b> we still use today — including <i>bedroom</i>, <i>lonely</i>, <i>generous</i>, <i>swagger</i>, and even <i>addiction</i>."),
    ("🤫", "The <b>shortest complete sentence</b> in English is just two letters: <i>\"Go.\"</i> (subject implied). But the longest published sentence has over <b>13,955 words</b> — in a William Faulkner novel!"),
    ("🐝", "The word <b>\"honeybee\"</b> is older than the word <b>\"honey\"</b> — ancient English had <i>hunig</i> for honey, but the bee part came first in compound words. Bees were named before their product!"),
    ("🌈", "English is one of the few languages that capitalizes the word <b>\"I\"</b>. Most other languages use a lowercase version of their first-person pronoun. It started as a style choice by medieval scribes."),
    ("🦁", "The word <b>\"muscle\"</b> literally means <i>\"little mouse\"</i> in Latin. Ancient Romans thought the movement of muscles under skin looked like a mouse running beneath fabric."),
    ("📱", "The average English speaker knows around <b>40,000–60,000 words</b> but uses only about <b>7,000–20,000</b> in everyday life. Your passive vocabulary is always bigger than your active one!"),
    ("🎭", "The phrase <b>\"break a leg\"</b> (meaning \"good luck\") may come from theatre: actors only got paid if they actually performed — which required \"breaking\" the leg line (the side curtain). Performing = breaking the leg = getting paid!"),
    ("🦆", "The <b>Oxford English Dictionary</b> has over <b>600,000 word entries</b> — the largest vocabulary of any language on Earth. But don't worry, you only need about 3,000 words to be fluent in everyday conversation."),
    ("⏰", "The word <b>\"deadline\"</b> has a dark origin. In American Civil War prisons, a literal line was drawn around the perimeter — cross it, and guards would shoot. Now it just means your boss will be unhappy."),
]

QUIZ_POOL = [
    {
        "question": "Which word means 'an extremely small amount of something'?",
        "options": ["Plethora", "Modicum", "Cascade", "Torrent"],
        "correct": 1,
        "explanation": "'Modicum' means a small quantity. 'Plethora' is the opposite — an excessive amount!",
    },
    {
        "question": "What does 'procrastinate' mean?",
        "options": ["To work very hard", "To delay doing something", "To celebrate success", "To speak publicly"],
        "correct": 1,
        "explanation": "To procrastinate = to delay tasks, often unnecessarily. 'I'll define this word later...'",
    },
    {
        "question": "Choose the correct sentence:",
        "options": [
            "She don't know the answer.",
            "She doesn't knows the answer.",
            "She doesn't know the answer.",
            "She not know the answer.",
        ],
        "correct": 2,
        "explanation": "With 'she/he/it' (3rd person singular), we use 'doesn't' + base verb (without -s).",
    },
    {
        "question": "What is the past tense of 'shrink'?",
        "options": ["Shrinked", "Shrank", "Shrunk", "Shrinking"],
        "correct": 1,
        "explanation": "Shrink → Shrank (past) → Shrunk (past participle). It's an irregular verb!",
    },
    {
        "question": "Which phrase is correct English?",
        "options": [
            "I am interesting in art.",
            "I am interested in art.",
            "I have interest to art.",
            "I be interested for art.",
        ],
        "correct": 1,
        "explanation": "'Interested in' is correct. Use 'interested' (how YOU feel), not 'interesting' (how something SEEMS to others).",
    },
    {
        "question": "What does the idiom 'to bite the bullet' mean?",
        "options": [
            "To eat something hard",
            "To shoot a gun",
            "To endure a difficult situation with courage",
            "To make a quick decision",
        ],
        "correct": 2,
        "explanation": "To 'bite the bullet' = endure pain or difficulty bravely. Originally, soldiers bit a bullet during surgery without anesthesia.",
    },
    {
        "question": "Which word is a synonym for 'verbose'?",
        "options": ["Silent", "Wordy", "Brief", "Angry"],
        "correct": 1,
        "explanation": "'Verbose' means using more words than needed. Synonyms: wordy, long-winded, prolix.",
    },
    {
        "question": "Complete the phrase: 'The ball is in your ___'",
        "options": ["hand", "side", "court", "field"],
        "correct": 2,
        "explanation": "'The ball is in your court' = it's your turn to take action or make a decision. From tennis!",
    },
    {
        "question": "What does 'ambiguous' mean?",
        "options": [
            "Completely clear",
            "Having two or more possible meanings",
            "Extremely large",
            "Morally wrong",
        ],
        "correct": 1,
        "explanation": "Ambiguous = unclear, open to interpretation. 'I saw the man with the telescope' is ambiguous — who has the telescope?",
    },
    {
        "question": "Which sentence uses the Present Perfect correctly?",
        "options": [
            "I have went to London last year.",
            "I have been to London.",
            "I was been to London.",
            "I have go to London.",
        ],
        "correct": 1,
        "explanation": "'Have been to' = visited a place (and returned). No specific time mentioned = Present Perfect ✓",
    },
]

MOTIVATIONS = [
    ("🌱", "\"Every expert was once a beginner.\"\n\nEvery English word you know today was once unknown to you. Keep going — your future self is fluent."),
    ("🔥", "\"Fluency is not a destination, it's a direction.\"\n\nYou don't need to be perfect to communicate. Start speaking before you feel ready."),
    ("🌊", "\"Learning a language is like swimming — you can only learn by getting in the water.\"\n\nRead in English. Think in English. Speak in English — even if it feels uncomfortable."),
    ("⭐", "\"The limits of my language are the limits of my world.\" — Ludwig Wittgenstein\n\nEvery new word expands your world. You're literally growing your reality."),
    ("🦋", "\"You don't have to be great to start, but you have to start to be great.\"\n\nOne lesson a day. One new word a day. In a year, you won't recognize yourself."),
    ("🏔️", "\"A language is a window to a new world.\"\n\nWith English, you get access to 55% of the internet, 90% of scientific research, and hundreds of millions of new people to connect with."),
    ("💎", "\"The beautiful thing about learning is that nobody can take it away from you.\" — B.B. King\n\nYour English skills are yours forever. Invest in yourself every day."),
    ("🚀", "\"Language learning is not a sprint — it's a marathon. But marathons can be run one step at a time.\"\n\nShow up today. That's all you need."),
    ("🌟", "\"Mistakes are proof that you are trying.\"\n\nEvery grammar error, every mispronounced word — it's evidence that you're brave enough to try. That's something to be proud of."),
    ("🎯", "\"The secret of getting ahead is getting started.\" — Mark Twain\n\nOpen the app. Do one exercise. Read one article. Start somewhere — even if somewhere feels small."),
]


def _format_word_of_day(word_data: dict) -> str:
    """Format a word dict into a Telegram HTML message."""
    emoji = random.choice(WORD_EMOJIS)
    word = word_data.get("word", "")
    translation = word_data.get("translation", "")
    ipa = word_data.get("ipa", "")
    level = word_data.get("level", "A2")
    example_en = word_data.get("example_en", "")
    example_ua = word_data.get("example_ua", "")

    badge = LEVEL_BADGES.get(level, f"📘 {level}")
    now = datetime.now(KYIV_TZ).strftime("%d.%m.%Y")

    lines = [
        f"{emoji} <b>Word of the Day</b> — {now}",
        "",
        f"<b>{word.upper()}</b>",
    ]
    if ipa:
        lines.append(f"<i>{ipa}</i>")
    lines.append("")
    lines.append(f"🇺🇦 <b>{translation}</b>")
    lines.append(f"📊 {badge}")
    if example_en:
        lines.append("")
        lines.append(f"💬 <i>{example_en}</i>")
    if example_ua:
        lines.append(f"   <i>{example_ua}</i>")
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append("📚 @VoodooEnglishBot | Навчайся щодня!")

    return "\n".join(lines)


def _format_fun_fact(emoji: str, fact_text: str) -> str:
    now = datetime.now(KYIV_TZ).strftime("%d.%m.%Y")
    return (
        f"🧠 <b>Fun English Fact</b> — {now}\n"
        f"\n"
        f"{emoji} {fact_text}\n"
        f"\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📚 @VoodooEnglishBot | Цікаво? Вчи англійську з нами!"
    )


def _format_motivation(emoji: str, quote: str) -> str:
    now = datetime.now(KYIV_TZ).strftime("%d.%m.%Y")
    return (
        f"💫 <b>Daily Motivation</b> — {now}\n"
        f"\n"
        f"{emoji} {quote}\n"
        f"\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🚀 Voodoo English Platform | Навчайся щодня!"
    )


# ── Post functions ─────────────────────────────────────────────────────────────

async def post_word_of_day(session: aiohttp.ClientSession, force: bool = False) -> bool:
    """Post Word of the Day to 📚 Teaching topic."""
    if not force and _already_posted("word_of_day"):
        log.info("Word of the Day already posted today, skipping.")
        return True

    thread_id = _get_thread_id("📚 Teaching", TOPIC_TEACHING)

    # Try DB first, fallback to hardcoded list
    word_data = _get_random_word()
    if not word_data:
        log.warning("No words in DB, using fallback word list.")
        word_data = random.choice(FALLBACK_WORDS)

    text = _format_word_of_day(word_data)
    ok = await send_message(session, thread_id, text)
    if ok:
        _mark_posted("word_of_day")
        log.info("Word of the Day posted: %s", word_data.get("word", "?"))
    return ok


async def post_fun_fact(session: aiohttp.ClientSession, force: bool = False) -> bool:
    """Post Fun English Fact to 📢 Content topic."""
    if not force and _already_posted("fun_fact"):
        log.info("Fun Fact already posted today, skipping.")
        return True

    thread_id = _get_thread_id("📢 Content", TOPIC_CONTENT)

    # Pick a fact not used recently
    state = _load_content_state()
    used_facts = set(state.get("used_fact_indices", []))
    available = [i for i in range(len(FUN_FACTS)) if i not in used_facts]
    if not available:
        available = list(range(len(FUN_FACTS)))
        state["used_fact_indices"] = []

    idx = random.choice(available)
    emoji, fact_text = FUN_FACTS[idx]

    state.setdefault("used_fact_indices", [])
    state["used_fact_indices"] = (state["used_fact_indices"] + [idx])[-len(FUN_FACTS):]
    _save_content_state(state)

    text = _format_fun_fact(emoji, fact_text)
    ok = await send_message(session, thread_id, text)
    if ok:
        _mark_posted("fun_fact")
        log.info("Fun Fact posted (idx=%d)", idx)
    return ok


async def post_mini_quiz(session: aiohttp.ClientSession, force: bool = False) -> bool:
    """Post Mini Quiz poll to 🧪 Testing topic."""
    if not force and _already_posted("mini_quiz"):
        log.info("Mini Quiz already posted today, skipping.")
        return True

    thread_id = _get_thread_id("🧪 Testing", TOPIC_TESTING)

    # Pick a quiz not used recently
    state = _load_content_state()
    used_quizzes = set(state.get("used_quiz_indices", []))
    available = [i for i in range(len(QUIZ_POOL)) if i not in used_quizzes]
    if not available:
        available = list(range(len(QUIZ_POOL)))
        state["used_quiz_indices"] = []

    idx = random.choice(available)
    quiz = QUIZ_POOL[idx]

    state.setdefault("used_quiz_indices", [])
    state["used_quiz_indices"] = (state["used_quiz_indices"] + [idx])[-len(QUIZ_POOL):]
    _save_content_state(state)

    now = datetime.now(KYIV_TZ).strftime("%d.%m.%Y")
    question = f"🧪 Mini Quiz — {now}\n\n{quiz['question']}"

    ok = await send_poll(
        session,
        thread_id,
        question=question,
        options=quiz["options"],
        correct_option_id=quiz["correct"],
        explanation=quiz.get("explanation", ""),
    )
    if ok:
        _mark_posted("mini_quiz")
        log.info("Mini Quiz posted (idx=%d)", idx)
    return ok


async def post_motivation(session: aiohttp.ClientSession, force: bool = False) -> bool:
    """Post Motivation quote to 📚 Teaching topic."""
    if not force and _already_posted("motivation"):
        log.info("Motivation already posted today, skipping.")
        return True

    thread_id = _get_thread_id("📚 Teaching", TOPIC_TEACHING)

    # Pick a motivation not used recently
    state = _load_content_state()
    used_motives = set(state.get("used_motive_indices", []))
    available = [i for i in range(len(MOTIVATIONS)) if i not in used_motives]
    if not available:
        available = list(range(len(MOTIVATIONS)))
        state["used_motive_indices"] = []

    idx = random.choice(available)
    emoji, quote = MOTIVATIONS[idx]

    state.setdefault("used_motive_indices", [])
    state["used_motive_indices"] = (state["used_motive_indices"] + [idx])[-len(MOTIVATIONS):]
    _save_content_state(state)

    text = _format_motivation(emoji, quote)
    ok = await send_message(session, thread_id, text)
    if ok:
        _mark_posted("motivation")
        log.info("Motivation posted (idx=%d)", idx)
    return ok


# ── Scheduler ──────────────────────────────────────────────────────────────────

SCHEDULE = [
    # (hour, minute, coroutine_name, label)
    (9,  0,  "word_of_day", "Word of the Day"),
    (13, 0,  "fun_fact",    "Fun Fact"),
    (18, 0,  "mini_quiz",   "Mini Quiz"),
    (21, 0,  "motivation",  "Motivation"),
]

POSTER_MAP = {
    "word_of_day": post_word_of_day,
    "fun_fact":    post_fun_fact,
    "mini_quiz":   post_mini_quiz,
    "motivation":  post_motivation,
}


async def run_scheduler() -> None:
    """Infinite loop that checks schedule every 30 seconds and posts at the right times."""
    log.info("Content Scheduler started. Group: %d", INTERNAL_GROUP_ID)
    log.info("Schedule (Kyiv time):")
    for h, m, name, label in SCHEDULE:
        log.info("  %02d:%02d — %s", h, m, label)

    fired_today: dict[str, str] = {}  # content_type → "YYYY-MM-DD HH:MM"

    async with aiohttp.ClientSession() as session:
        while True:
            now = datetime.now(KYIV_TZ)
            today_str = str(now.date())

            for hour, minute, content_type, label in SCHEDULE:
                key = f"{today_str}_{content_type}"
                if key in fired_today:
                    continue  # already fired this slot today

                # Fire if we're within the minute window
                if now.hour == hour and now.minute == minute:
                    log.info("Firing: %s at %02d:%02d Kyiv", label, hour, minute)
                    try:
                        poster_fn = POSTER_MAP[content_type]
                        ok = await poster_fn(session, force=True)
                        fired_today[key] = now.strftime("%Y-%m-%d %H:%M")
                        log.info("%s posted: %s", label, ok)
                    except Exception as exc:
                        log.error("Failed to post %s: %s", label, exc)

            # Clean up fired_today for previous days
            fired_today = {k: v for k, v in fired_today.items() if k.startswith(today_str)}

            await asyncio.sleep(30)


async def post_all_now(force: bool = True) -> None:
    """Post all content types immediately (for testing)."""
    log.info("Posting all content NOW (force=%s)", force)
    async with aiohttp.ClientSession() as session:
        results = {}
        results["word_of_day"] = await post_word_of_day(session, force=force)
        await asyncio.sleep(1)
        results["fun_fact"]    = await post_fun_fact(session, force=force)
        await asyncio.sleep(1)
        results["mini_quiz"]   = await post_mini_quiz(session, force=force)
        await asyncio.sleep(1)
        results["motivation"]  = await post_motivation(session, force=force)

    log.info("Results: %s", results)
    return results


# ── CLI entry point ────────────────────────────────────────────────────────────

async def _main() -> None:
    if not BOT_TOKEN:
        print("ERROR: VOODOO_OPS_BOT_TOKEN not set in .env")
        sys.exit(1)
    if not INTERNAL_GROUP_ID:
        print("ERROR: INTERNAL_GROUP_ID not set in .env")
        sys.exit(1)

    args = sys.argv[1:]

    async with aiohttp.ClientSession() as session:
        if "--now" in args:
            await post_all_now(force=True)
        elif "--word" in args:
            await post_word_of_day(session, force=True)
        elif "--fact" in args:
            await post_fun_fact(session, force=True)
        elif "--quiz" in args:
            await post_mini_quiz(session, force=True)
        elif "--motive" in args:
            await post_motivation(session, force=True)
        else:
            # Default: run scheduler
            await run_scheduler()


if __name__ == "__main__":
    asyncio.run(_main())
