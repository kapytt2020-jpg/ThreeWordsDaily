"""
Mini App API — FastAPI backend for ThreeWordsDaily
Run: uvicorn api:app --reload --port 8000
"""

import sys
import os

# Try parent dir first (local), then same dir (Vercel)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import random
from datetime import date, timedelta
from typing import Optional

# Curriculum integration (optional — works without it)
try:
    from content_plan_9months import get_current_week_plan, get_daily_words
    _CURRICULUM = True
except ImportError:
    _CURRICULUM = False

from dotenv import load_dotenv

# Load .env from parent or current dir
for _env_path in [
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
]:
    if os.path.exists(_env_path):
        load_dotenv(dotenv_path=_env_path)
        break

from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import AsyncOpenAI

# Database — optional (works locally with SQLite, falls back to in-memory on Vercel)
try:
    import database
    DB_AVAILABLE = True
except ImportError:
    database = None
    DB_AVAILABLE = False

# In-memory fallback store (for Vercel serverless — resets on cold start)
_mem_users: dict = {}
_mem_lessons: dict = {}
_mem_rewards: dict = {}  # tg_id -> set of badge_ids


# ===== DB WRAPPER (SQLite locally / in-memory on Vercel) =====

async def db_init():
    if DB_AVAILABLE:
        await database.init_db()
        # Auto-migration: add premium columns if missing
        import aiosqlite, os as _os
        _db_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "threewords.db")
        async with aiosqlite.connect(_db_path) as _conn:
            for _col, _def in [
                ("is_premium",       "INTEGER DEFAULT 0"),
                ("premium_expires",  "TEXT DEFAULT NULL"),
                ("stars_spent",      "INTEGER DEFAULT 0"),
            ]:
                try:
                    await _conn.execute(f"ALTER TABLE users ADD COLUMN {_col} {_def}")
                    await _conn.commit()
                except Exception:
                    pass  # column already exists

async def db_get_or_create_user(tg_id: int, first_name: str = "", username: str = "") -> dict:
    if DB_AVAILABLE:
        return await database.get_or_create_user(tg_id, first_name, username)
    if tg_id not in _mem_users:
        _mem_users[tg_id] = {
            "tg_id": tg_id, "first_name": first_name, "username": username,
            "level": "A2", "topic": "everyday", "xp": 0, "streak": 0,
            "last_lesson_date": None, "words_learned": "[]",
            "total_lessons": 0, "total_quizzes": 0, "correct_answers": 0,
            "referrals_count": 0, "pet_hp": 50, "pet_xp": 0,
        }
    else:
        if first_name: _mem_users[tg_id]["first_name"] = first_name
    return _mem_users[tg_id]

async def db_get_user(tg_id: int) -> dict | None:
    if DB_AVAILABLE:
        return await database.get_user(tg_id)
    return _mem_users.get(tg_id)

async def db_update_user(tg_id: int, **fields):
    if DB_AVAILABLE:
        await database.update_user(tg_id, **fields)
    if tg_id in _mem_users:
        _mem_users[tg_id].update(fields)

async def db_get_user_stats(tg_id: int) -> dict:
    if DB_AVAILABLE:
        return await database.get_user_stats(tg_id)
    u = _mem_users.get(tg_id, {})
    xp = u.get("xp", 0)
    rank_label = "🌱 Новачок"
    for xp_min, label in [(1000,"👑 Майстер"),(500,"💎 Експерт"),(200,"🔥 Практик"),(50,"⚡ Учень")]:
        if xp >= xp_min: rank_label = label; break
    pos = sorted(_mem_users.values(), key=lambda x: x.get("xp",0), reverse=True)
    rank_pos = next((i+1 for i,u2 in enumerate(pos) if u2.get("tg_id")==tg_id), 1)
    return {"rank": rank_pos, "rank_label": rank_label}

async def db_get_leaderboard(limit: int = 10) -> list:
    if DB_AVAILABLE:
        return await database.get_leaderboard(limit)
    sorted_u = sorted(_mem_users.values(), key=lambda x: x.get("xp",0), reverse=True)
    return [{"rank": i+1, "tg_id": u.get("tg_id"), "first_name": u.get("first_name","?"),
             "xp": u.get("xp",0), "streak": u.get("streak",0),
             "words_count": len(json.loads(u.get("words_learned","[]"))), "is_me": False}
            for i,u in enumerate(sorted_u[:limit])]

async def db_cache_lesson(level: str, topic: str, date_str: str, lesson_json: str):
    if DB_AVAILABLE:
        await database.cache_lesson(level, topic, date_str, lesson_json)
    _mem_lessons[f"{level}:{topic}:{date_str}"] = lesson_json

async def db_get_cached_lesson(level: str, topic: str, date_str: str) -> dict | None:
    if DB_AVAILABLE:
        return await database.get_cached_lesson(level, topic, date_str)
    raw = _mem_lessons.get(f"{level}:{topic}:{date_str}")
    return json.loads(raw) if raw else None

async def db_add_reward(tg_id: int, badge_id: str) -> bool:
    if DB_AVAILABLE:
        return await database.add_reward(tg_id, badge_id)
    s = _mem_rewards.setdefault(tg_id, set())
    if badge_id in s: return False
    s.add(badge_id); return True

async def db_get_rewards(tg_id: int) -> list:
    if DB_AVAILABLE:
        return await database.get_rewards(tg_id)
    return [{"badge_id": b, "earned_at": str(date.today())} for b in _mem_rewards.get(tg_id, set())]

async def db_add_progress_event(tg_id: int, event_type: str, xp_earned: int, data: dict = {}):
    if DB_AVAILABLE:
        await database.add_progress_event(tg_id, event_type, xp_earned, data)


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MINI_APP_DIR = os.path.dirname(os.path.abspath(__file__))
# DB path — env override for Docker (/app/data/threewords.db), fallback to local
_LOCAL_DB = os.path.join(MINI_APP_DIR, "threewords.db")
CLOUD_DB_PATH = os.getenv("DB_PATH", _LOCAL_DB)

openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

app = FastAPI(title="ThreeWordsDaily API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== BADGE DEFINITIONS =====

ALL_BADGES = [
    {"id": "first_lesson",  "name": "Перший урок",       "icon": "🎓", "desc": "Пройти перший урок"},
    {"id": "streak_3",      "name": "Streak 3 дні",      "icon": "🔥", "desc": "3 дні поспіль"},
    {"id": "streak_7",      "name": "Streak 7 днів",     "icon": "🌟", "desc": "7 днів поспіль"},
    {"id": "words_10",      "name": "10 слів",           "icon": "📚", "desc": "Вивчити 10 слів"},
    {"id": "words_50",      "name": "50 слів",           "icon": "📖", "desc": "Вивчити 50 слів"},
    {"id": "quiz_master",   "name": "Quiz Master",       "icon": "🧠", "desc": "10 тестів пройдено"},
    {"id": "perfect_quiz",  "name": "Ідеальний тест",    "icon": "💯", "desc": "Всі відповіді вірні"},
    {"id": "early_bird",    "name": "Рання пташка",      "icon": "🐦", "desc": "Урок до 9 ранку"},
    {"id": "social",        "name": "Соціальний",        "icon": "👥", "desc": "Запросити 1 друга"},
]

# ===== PET HELPERS =====

PET_STAGES = [
    {"stage": 0, "name": "Яйце",     "emoji": "🥚",  "min_words": 0},
    {"stage": 1, "name": "Малюк",    "emoji": "🐣",  "min_words": 10},
    {"stage": 2, "name": "Пташеня",  "emoji": "🐥",  "min_words": 30},
    {"stage": 3, "name": "Пташка",   "emoji": "🐦",  "min_words": 60},
    {"stage": 4, "name": "Орел",     "emoji": "🦅",  "min_words": 100},
]

PET_MOODS = [
    {"mood": 0, "name": "Сонний",    "emoji": "😴", "streak_min": 0},
    {"mood": 1, "name": "Радісний",  "emoji": "😊", "streak_min": 1},
    {"mood": 2, "name": "Щасливий",  "emoji": "🤩", "streak_min": 3},
    {"mood": 3, "name": "Зоряний",   "emoji": "🌟", "streak_min": 7},
]

PET_MESSAGES = {
    0: "Лексик спить... Зроби урок, щоб розбудити! 😴",
    1: "Лексик радіє твоєму прогресу! 😊",
    2: "Лексик в захваті від твого streak! 🤩",
    3: "Лексик досяг зіркового настрою! Ти легенда! 🌟",
}


def compute_pet_stage(words_learned_count: int) -> dict:
    stage_info = PET_STAGES[0]
    for s in PET_STAGES:
        if words_learned_count >= s["min_words"]:
            stage_info = s
    return stage_info


def compute_pet_mood(streak: int, has_lesson_today: bool) -> dict:
    if not has_lesson_today:
        return PET_MOODS[0]
    mood_info = PET_MOODS[1]
    for m in PET_MOODS:
        if streak >= m["streak_min"]:
            mood_info = m
    return mood_info


def build_pet_response(user: dict) -> dict:
    words_list = json.loads(user.get("words_learned") or "[]")
    words_count = len(words_list)
    streak = user.get("streak", 0)
    last_lesson = user.get("last_lesson_date")
    today = str(date.today())
    has_lesson_today = (last_lesson == today)

    stage_info = compute_pet_stage(words_count)
    mood_info = compute_pet_mood(streak, has_lesson_today)
    message = PET_MESSAGES.get(mood_info["mood"], "")

    return {
        "stage": stage_info["stage"],
        "stage_name": stage_info["name"],
        "emoji": stage_info["emoji"],
        "mood": mood_info["mood"],
        "mood_name": mood_info["name"],
        "mood_emoji": mood_info["emoji"],
        "hp": user.get("pet_hp", 50),
        "xp": user.get("pet_xp", 0),
        "message": message,
    }


# ===== FALLBACK LESSON =====

FALLBACK_LESSON = {
    "words": [
        {
            "word": "resilient",
            "transcription": "/rɪˈzɪliənt/",
            "translation": "стійкий",
            "example": "She's incredibly resilient under pressure.",
            "example_ua": "Вона неймовірно стійка під тиском.",
        },
        {
            "word": "ambitious",
            "transcription": "/æmˈbɪʃəs/",
            "translation": "амбітний",
            "example": "He's ambitious about his career goals.",
            "example_ua": "Він амбітний щодо своїх кар'єрних цілей.",
        },
        {
            "word": "persistent",
            "transcription": "/pərˈsɪstənt/",
            "translation": "наполегливий",
            "example": "Persistent effort leads to success.",
            "example_ua": "Наполеглива праця веде до успіху.",
        },
    ],
    "idiom": {
        "text": "break a leg",
        "translation": "ні пуху ні пера (удачі)",
        "example": "Break a leg in your presentation!",
        "example_ua": "Удачі на презентації!",
    },
    "mini_story": "Alex was resilient and ambitious. Despite failures, he remained persistent and eventually succeeded.",
    "mini_story_ua": "Алекс був стійким та амбітним. Незважаючи на невдачі, він залишався наполегливим і врешті досяг успіху.",
    "quiz": [
        {
            "question": "Що означає слово 'resilient'?",
            "answers": ["стійкий", "слабкий", "швидкий", "тихий"],
            "correct": 0,
        },
        {
            "question": "Що означає слово 'ambitious'?",
            "answers": ["ледачий", "амбітний", "спокійний", "сумний"],
            "correct": 1,
        },
        {
            "question": "Що означає слово 'persistent'?",
            "answers": ["повільний", "хаотичний", "наполегливий", "байдужий"],
            "correct": 2,
        },
    ],
}


def build_quiz_for_words(words: list) -> list:
    wrong_pool = [
        "втомлений", "сміливий", "щасливий", "серйозний",
        "спокійний", "розчарований", "цікавий", "складний",
        "дружній", "активний", "ефективний", "важкий",
        "веселий", "сумний", "розумний", "тихий",
        "швидкий", "повільний", "сильний", "слабкий",
    ]
    quiz = []
    for w in words:
        bad = [x for x in wrong_pool if x != w["translation"]]
        wrongs = random.sample(bad, min(3, len(bad)))
        answers = [w["translation"]] + wrongs
        random.shuffle(answers)
        correct_idx = answers.index(w["translation"])
        quiz.append({
            "question": f"Що означає слово '{w['word']}' {w.get('transcription', '')}?",
            "answers": answers,
            "correct": correct_idx,
        })
    return quiz


async def check_and_award_badges(tg_id: int, user: dict) -> list:
    """Check badge conditions and award new ones. Returns list of newly awarded badge IDs."""
    new_badges = []
    words_list = json.loads(user.get("words_learned") or "[]")
    words_count = len(words_list)

    conditions = {
        "first_lesson": user.get("total_lessons", 0) >= 1,
        "streak_3": user.get("streak", 0) >= 3,
        "streak_7": user.get("streak", 0) >= 7,
        "words_10": words_count >= 10,
        "words_50": words_count >= 50,
        "quiz_master": user.get("total_quizzes", 0) >= 10,
        "social": user.get("referrals_count", 0) >= 1,
    }

    for badge_id, condition in conditions.items():
        if condition:
            added = await db_add_reward(tg_id, badge_id)
            if added:
                new_badges.append(badge_id)

    return new_badges


# ===== PYDANTIC MODELS =====

class UserInitBody(BaseModel):
    tg_init_data: str
    user: Optional[dict] = None


class ProgressBody(BaseModel):
    tg_id: int
    event_type: str
    xp_earned: int = 0
    words_learned: list = []
    data: dict = {}


class PetInteractBody(BaseModel):
    tg_id: int
    action: str  # feed | play | talk


class UpdateSettingsBody(BaseModel):
    tg_id: int
    topic: Optional[str] = None
    level: Optional[str] = None


class PetSelectBody(BaseModel):
    tg_id: int
    pet_character: str   # e.g. "lumix", "kitsune", "mochi", "byte", "ember", "mist", "marco", "astro", "crash"
    pet_name: Optional[str] = None


# ===== STARTUP =====

@app.on_event("startup")
async def startup():
    await db_init()


# ===== ENDPOINTS =====

@app.post("/api/user/init")
async def user_init(body: UserInitBody):
    # Determine user info
    if body.tg_init_data == "demo" and body.user:
        tg_id = int(body.user.get("id", 0)) or 999999
        first_name = body.user.get("first_name", "Demo")
        username = body.user.get("username", "demo")
    else:
        # Accept real initData or extract from user field
        user_data = body.user or {}
        tg_id = int(user_data.get("id", 0)) or 999999
        first_name = user_data.get("first_name", "Друже")
        username = user_data.get("username", "")

    user = await db_get_or_create_user(tg_id, first_name, username)

    # Streak update
    today = str(date.today())
    yesterday = str(date.today() - timedelta(days=1))
    last = user.get("last_lesson_date")
    streak = user.get("streak", 0)

    if last != today:
        if last == yesterday:
            streak += 1
        elif last is None:
            streak = 0
        # Don't reset streak on login, only on lesson events
        await db_update_user(tg_id, streak=streak)
        user["streak"] = streak

    await db_add_progress_event(tg_id, "login", 0)

    # Build response
    words_list = json.loads(user.get("words_learned") or "[]")
    stats = await db_get_user_stats(tg_id)
    badges = await db_get_rewards(tg_id)
    pet = build_pet_response(user)

    return {
        "tg_id": tg_id,
        "first_name": first_name,
        "xp": user.get("xp", 0),
        "streak": user.get("streak", 0),
        "level": user.get("level", "A2"),
        "topic": user.get("topic", "everyday"),
        "words_learned": words_list,
        "pet": pet,
        "rank": stats.get("rank", 1),
        "rank_label": stats.get("rank_label", "🌱 Новачок"),
        "badges": [b["badge_id"] for b in badges],
        "total_lessons": user.get("total_lessons", 0),
        "total_quizzes": user.get("total_quizzes", 0),
        "referrals_count": user.get("referrals_count", 0),
        "pet_character": user.get("pet_character"),
        "pet_name": user.get("pet_name"),
        "is_premium": bool(user.get("is_premium", 0)),
        "premium_expires": user.get("premium_expires"),
    }


@app.post("/api/user/pet/select")
async def pet_select(body: PetSelectBody):
    """Save the user's chosen pet character and name to the database."""
    VALID_CHARS = {"lumix","kitsune","mochi","byte","ember","mist","marco","astro","bruno","crash",
                   "nova","luna","rex","sunny","biscuit","ronin","apex","bolt",
                   "kaito","yuki","vex","seraph",  # preview6 characters
                   "spirit","beast","buddy"}  # legacy archetypes also accepted
    char = body.pet_character.lower().strip()
    if char not in VALID_CHARS:
        return {"ok": False, "error": "Unknown character"}
    name = (body.pet_name or "").strip()[:20] or None
    await db_update_user(body.tg_id, pet_character=char, pet_name=name or None)
    if body.tg_id in _mem_users:
        _mem_users[body.tg_id]["pet_character"] = char
        if name:
            _mem_users[body.tg_id]["pet_name"] = name
    return {"ok": True, "pet_character": char, "pet_name": name}


@app.get("/api/lesson")
async def get_lesson(tg_id: int = Query(...)):
    user = await db_get_user(tg_id)
    if not user:
        return FALLBACK_LESSON

    level = user.get("level") or "A2"
    topic = user.get("topic") or "everyday"
    today = str(date.today())

    # Check cache
    cached = await db_get_cached_lesson(level, topic, today)
    if cached:
        return cached

    # Generate via OpenAI
    topic_names = {
        "work": "Робота та бізнес",
        "travel": "Подорожі",
        "everyday": "Повсякденне",
        "emotions": "Емоції",
        "technology": "Технології",
        "mixed": "різні теми",
    }
    topic_ua = topic_names.get(topic, topic)

    # Build curriculum context for today's lesson
    curriculum_hint = ""
    if _CURRICULUM:
        plan = get_current_week_plan()
        if plan:
            today_weekday = date.today().weekday() + 1  # 1=Mon..5=Fri
            day_words = get_daily_words(plan["month"], plan["week"], min(today_weekday, 5))
            if day_words:
                words_ctx = ", ".join(
                    f"{w['en']} ({w['ua']})" for w in day_words
                )
                curriculum_hint = (
                    f"\nThis week's theme: {plan['theme']}. "
                    f"Grammar focus: {plan['grammar']}. "
                    f"Preferred words for today: {words_ctx}. "
                    f"Idiom context: {plan['idiom']} — {plan['idiom_meaning']}."
                )

    try:
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
Тема: {topic_ua}{curriculum_hint}

Поверни ТІЛЬКИ JSON:
{{
  "words": [
    {{
      "word": "...",
      "transcription": "/.../",
      "translation": "...",
      "example": "...",
      "example_ua": "..."
    }}
  ],
  "idiom": {{
    "text": "...",
    "translation": "...",
    "example": "...",
    "example_ua": "..."
  }},
  "mini_story": "2-3 sentence story using all 3 words in English.",
  "mini_story_ua": "Переклад story українською."
}}

Рівно 3 слова. Тема: {topic_ua}. Рівень: {level}.""",
                },
            ],
            max_tokens=1200,
            temperature=0.8,
        )
        raw = resp.choices[0].message.content.strip()
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
        lesson = json.loads(raw.strip())

        # Build quiz from words
        lesson["quiz"] = build_quiz_for_words(lesson.get("words", []))

        # Cache it
        await db_cache_lesson(level, topic, today, json.dumps(lesson))
        return lesson

    except Exception as e:
        # Return fallback with error note
        fallback = dict(FALLBACK_LESSON)
        fallback["_fallback"] = True
        return fallback


@app.post("/api/progress")
async def save_progress(body: ProgressBody):
    tg_id = body.tg_id
    user = await db_get_user(tg_id)
    if not user:
        return {"ok": False, "error": "User not found"}

    # Merge words_learned
    existing_words = json.loads(user.get("words_learned") or "[]")
    new_words = list(set(existing_words + body.words_learned))

    # Update XP
    new_xp = user.get("xp", 0) + body.xp_earned

    # Update streak if lesson event
    today = str(date.today())
    yesterday = str(date.today() - timedelta(days=1))
    streak = user.get("streak", 0)
    last = user.get("last_lesson_date")

    if body.event_type == "lesson":
        if last != today:
            if last == yesterday:
                streak += 1
            else:
                streak = 1

    # Update pet
    pet_hp = min(100, user.get("pet_hp", 50) + 10)
    pet_xp = user.get("pet_xp", 0) + body.xp_earned

    # Update lesson/quiz counts
    total_lessons = user.get("total_lessons", 0)
    total_quizzes = user.get("total_quizzes", 0)
    correct_answers = user.get("correct_answers", 0)

    if body.event_type == "lesson":
        total_lessons += 1
    if body.event_type == "quiz":
        total_quizzes += 1
        correct_answers += body.data.get("correct_count", 0)

    # Increment weekly XP
    new_weekly_xp = (user.get("weekly_xp") or 0) + body.xp_earned

    update_fields = {
        "xp": new_xp,
        "weekly_xp": new_weekly_xp,
        "words_learned": json.dumps(new_words),
        "streak": streak,
        "pet_hp": pet_hp,
        "pet_xp": pet_xp,
        "total_lessons": total_lessons,
        "total_quizzes": total_quizzes,
        "correct_answers": correct_answers,
    }
    if body.event_type == "lesson":
        update_fields["last_lesson_date"] = today

    await db_update_user(tg_id, **update_fields)
    await db_add_progress_event(tg_id, body.event_type, body.xp_earned, body.data)

    # Refresh user for badge check
    user_updated = await db_get_user(tg_id)
    new_badges = await check_and_award_badges(tg_id, user_updated)

    # Perfect quiz badge
    if body.event_type == "quiz" and body.data.get("all_correct"):
        added = await db_add_reward(tg_id, "perfect_quiz")
        if added:
            new_badges.append("perfect_quiz")

    pet = build_pet_response(user_updated)

    return {
        "ok": True,
        "new_xp": new_xp,
        "streak": streak,
        "pet": pet,
        "new_badges": new_badges,
        "words_count": len(new_words),
    }


@app.get("/api/leaderboard")
async def get_leaderboard(tg_id: int = Query(0)):
    leaders = await db_get_leaderboard(limit=10)

    # Mark caller
    caller_in_top = False
    for entry in leaders:
        entry["is_me"] = (entry["tg_id"] == tg_id)
        if entry["tg_id"] == tg_id:
            caller_in_top = True

    # If caller not in top 10, get their position
    if tg_id and not caller_in_top:
        user = await db_get_user(tg_id)
        if user:
            pos = len(leaders) + 1
            if DB_AVAILABLE:
                try:
                    import aiosqlite
                    async with aiosqlite.connect(database.DB_PATH) as db:
                        async with db.execute(
                            "SELECT COUNT(*) FROM users WHERE xp > ?", (user.get("xp", 0),)
                        ) as cur:
                            row = await cur.fetchone()
                            pos = (row[0] + 1) if row else pos
                except Exception:
                    pass
            words_count = len(json.loads(user.get("words_learned") or "[]"))
            leaders.append({
                "rank": pos,
                "tg_id": tg_id,
                "first_name": user.get("first_name", "Ти"),
                "xp": user.get("xp", 0),
                "streak": user.get("streak", 0),
                "words_count": words_count,
                "is_me": True,
            })

    return leaders


@app.get("/api/pet")
async def get_pet(tg_id: int = Query(...)):
    user = await db_get_user(tg_id)
    if not user:
        return {"error": "User not found"}
    return build_pet_response(user)


@app.get("/api/badges")
async def get_badges(tg_id: int = Query(...)):
    user = await db_get_user(tg_id)
    if not user:
        return []

    earned = await db_get_rewards(tg_id)
    earned_ids = {r["badge_id"] for r in earned}

    result = []
    for badge in ALL_BADGES:
        b = dict(badge)
        b["unlocked"] = badge["id"] in earned_ids
        if b["unlocked"]:
            earned_badge = next((r for r in earned if r["badge_id"] == badge["id"]), None)
            b["earned_at"] = earned_badge["earned_at"] if earned_badge else None
        result.append(b)

    return result


@app.post("/api/interact/pet")
async def interact_pet(body: PetInteractBody):
    tg_id = body.tg_id
    user = await db_get_user(tg_id)
    if not user:
        return {"error": "User not found"}

    today = str(date.today())
    last_lesson = user.get("last_lesson_date")
    has_lesson_today = (last_lesson == today)

    pet_hp = user.get("pet_hp", 50)
    pet_xp = user.get("pet_xp", 0)
    message = ""

    if body.action == "feed":
        if not has_lesson_today:
            return {
                "ok": False,
                "message": "Спочатку зроби урок дня, щоб нагодувати Лексика! 📚",
                "pet": build_pet_response(user),
            }
        pet_hp = min(100, pet_hp + 20)
        pet_xp += 5
        message = "Лексик ситий та щасливий! 🍎✨"

    elif body.action == "play":
        pet_hp = min(100, pet_hp + 10)
        pet_xp += 3
        message = "Лексик грає і радіє! 🎮😊"

    elif body.action == "talk":
        pet_hp = min(100, pet_hp + 5)
        message = "Лексик слухає тебе з задоволенням! 💬🐣"

    else:
        return {"ok": False, "error": "Unknown action"}

    await db_update_user(tg_id, pet_hp=pet_hp, pet_xp=pet_xp)
    updated_user = await db_get_user(tg_id)
    pet = build_pet_response(updated_user)

    return {
        "ok": True,
        "message": message,
        "pet": pet,
    }


@app.post("/api/settings")
async def update_settings(body: UpdateSettingsBody):
    fields = {}
    if body.topic:
        fields["topic"] = body.topic
    if body.level:
        fields["level"] = body.level
    if fields:
        await db_update_user(body.tg_id, **fields)
    return {"ok": True}


# ===== STATUS & CURRICULUM ENDPOINTS =====

@app.get("/api/status")
async def get_status():
    """Live group stats + current curriculum week — used by mini app for auto-update."""
    stats = {}
    if DB_AVAILABLE:
        try:
            from datetime import timedelta
            import sqlite3 as _sqlite3
            conn = _sqlite3.connect(str(database.DB_FILE), timeout=5)
            today = str(date.today())
            week_ago = str(date.today() - timedelta(days=7))
            total = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            active_today = conn.execute(
                "SELECT COUNT(*) FROM users WHERE last_lesson_date=?", (today,)
            ).fetchone()[0]
            active_week = conn.execute(
                "SELECT COUNT(*) FROM users WHERE last_lesson_date>=?", (week_ago,)
            ).fetchone()[0]
            avg_streak = conn.execute("SELECT AVG(streak) FROM users").fetchone()[0] or 0
            conn.close()
            stats = {
                "total_users": total,
                "active_today": active_today,
                "active_week": active_week,
                "avg_streak": round(avg_streak, 1),
            }
        except Exception:
            pass

    curriculum = {}
    if _CURRICULUM:
        plan = get_current_week_plan()
        if plan:
            curriculum = {
                "month": plan["month"],
                "week": plan["week"],
                "theme": plan["theme"],
                "grammar": plan["grammar"],
                "idiom": plan["idiom"],
                "idiom_meaning": plan["idiom_meaning"],
            }

    return {"ok": True, "stats": stats, "curriculum": curriculum}


@app.get("/api/curriculum")
async def get_curriculum():
    """Return full current week curriculum plan for mini app display."""
    if not _CURRICULUM:
        return {"ok": False, "error": "Curriculum not available"}
    plan = get_current_week_plan()
    if not plan:
        return {"ok": False, "error": "No plan for current week"}
    today_weekday = date.today().weekday() + 1
    today_words = get_daily_words(plan["month"], plan["week"], min(today_weekday, 5))
    return {
        "ok": True,
        "theme": plan["theme"],
        "grammar": plan["grammar"],
        "idiom": plan["idiom"],
        "idiom_meaning": plan["idiom_meaning"],
        "mini_story_prompt": plan["mini_story_prompt"],
        "today_words": today_words,
        "all_words": plan["words"],
    }


# ===== PREMIUM / MONETIZATION =====

PREMIUM_PRICE_STARS = 75  # 75 Telegram Stars ≈ $1.5/month
PREMIUM_DAYS = 30

class PremiumActivateBody(BaseModel):
    tg_id: int
    stars: int  # number of Stars paid (verified by learning_bot webhook)
    secret: str  # shared secret so only our bot can call this

PREMIUM_SECRET = os.getenv("PREMIUM_SECRET", "twd_premium_secret_2026")

@app.post("/api/premium/activate")
async def premium_activate(body: PremiumActivateBody):
    """Called by learning_bot after successful Telegram Stars payment."""
    if body.secret != PREMIUM_SECRET:
        return {"ok": False, "error": "Unauthorized"}
    if body.stars < PREMIUM_PRICE_STARS:
        return {"ok": False, "error": f"Need {PREMIUM_PRICE_STARS} stars, got {body.stars}"}
    from datetime import datetime, timedelta
    expires = (datetime.utcnow() + timedelta(days=PREMIUM_DAYS)).strftime("%Y-%m-%d")
    if DB_AVAILABLE:
        import aiosqlite, os as _os
        _db_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "threewords.db")
        async with aiosqlite.connect(_db_path) as conn:
            await conn.execute(
                "UPDATE users SET is_premium=1, premium_expires=?, stars_spent=stars_spent+? WHERE tg_id=?",
                (expires, body.stars, body.tg_id)
            )
            await conn.commit()
    return {"ok": True, "premium_expires": expires, "message": f"✅ Premium активовано до {expires}"}

@app.get("/api/premium/status")
async def premium_status(tg_id: int):
    """Check if user has active premium."""
    from datetime import datetime
    if DB_AVAILABLE:
        import aiosqlite, os as _os
        _db_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "threewords.db")
        async with aiosqlite.connect(_db_path) as conn:
            async with conn.execute(
                "SELECT is_premium, premium_expires, stars_spent FROM users WHERE tg_id=?", (tg_id,)
            ) as cur:
                row = await cur.fetchone()
        if not row:
            return {"is_premium": False}
        is_prem, expires, stars = row
        if is_prem and expires:
            still_active = datetime.utcnow().strftime("%Y-%m-%d") <= expires
            if not still_active:
                # Expire it
                async with aiosqlite.connect(_db_path) as conn:
                    await conn.execute("UPDATE users SET is_premium=0 WHERE tg_id=?", (tg_id,))
                    await conn.commit()
                return {"is_premium": False, "expired": expires}
            return {"is_premium": True, "expires": expires, "stars_spent": stars}
    return {"is_premium": False}


# ===== DAILY LOGIN BONUS =====

@app.get("/api/daily-bonus")
async def get_daily_bonus(tg_id: int):
    from zoneinfo import ZoneInfo
    from datetime import datetime
    today = datetime.now(ZoneInfo("Europe/Kyiv")).strftime("%Y-%m-%d")
    async with aiosqlite.connect(CLOUD_DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        user = await (await conn.execute(
            "SELECT last_login_date, login_streak_day, streak_freeze FROM users WHERE tg_id=?", (tg_id,)
        )).fetchone()
        if not user:
            return {"available": False}

        last = user["last_login_date"]
        day = user["login_streak_day"] or 0

        if last == today:
            return {"available": False, "day": day}

        # Escalating rewards: day 1-7 then reset
        rewards = [
            {"xp": 10, "hp": 5, "label": "День 1"},
            {"xp": 15, "hp": 5, "label": "День 2"},
            {"xp": 20, "hp": 10, "label": "День 3"},
            {"xp": 25, "hp": 10, "label": "День 4 🔥"},
            {"xp": 30, "hp": 15, "label": "День 5 🔥"},
            {"xp": 40, "hp": 15, "label": "День 6 🔥"},
            {"xp": 75, "hp": 25, "label": "День 7 🌟"},
        ]
        next_day = (day % 7)
        return {"available": True, "day": next_day, "reward": rewards[next_day]}

@app.post("/api/daily-bonus/claim")
async def claim_daily_bonus(data: dict):
    from zoneinfo import ZoneInfo
    from datetime import datetime
    tg_id = data.get("tg_id")
    today = datetime.now(ZoneInfo("Europe/Kyiv")).strftime("%Y-%m-%d")

    rewards = [10, 15, 20, 25, 30, 40, 75]
    hp_rewards = [5, 5, 10, 10, 15, 15, 25]

    async with aiosqlite.connect(CLOUD_DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        user = await (await conn.execute(
            "SELECT last_login_date, login_streak_day, xp, pet_hp FROM users WHERE tg_id=?", (tg_id,)
        )).fetchone()
        if not user or user["last_login_date"] == today:
            return {"ok": False, "reason": "already_claimed"}

        day = (user["login_streak_day"] or 0) % 7
        xp_bonus = rewards[day]
        hp_bonus = hp_rewards[day]
        new_day = day + 1
        new_xp = (user["xp"] or 0) + xp_bonus
        new_hp = min(100, (user["pet_hp"] or 50) + hp_bonus)

        await conn.execute(
            "UPDATE users SET last_login_date=?, login_streak_day=?, xp=?, pet_hp=? WHERE tg_id=?",
            (today, new_day, new_xp, new_hp, tg_id)
        )
        await conn.commit()
        return {"ok": True, "day": day, "xp_bonus": xp_bonus, "hp_bonus": hp_bonus, "new_xp": new_xp}


# ===== STREAK FREEZE =====

@app.post("/api/streak-freeze/use")
async def use_streak_freeze(data: dict):
    from zoneinfo import ZoneInfo
    from datetime import datetime
    tg_id = data.get("tg_id")
    async with aiosqlite.connect(CLOUD_DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        user = await (await conn.execute(
            "SELECT streak_freeze, streak, last_lesson_date FROM users WHERE tg_id=?", (tg_id,)
        )).fetchone()
        if not user or (user["streak_freeze"] or 0) <= 0:
            return {"ok": False, "reason": "no_freeze"}

        today = datetime.now(ZoneInfo("Europe/Kyiv")).strftime("%Y-%m-%d")
        await conn.execute(
            "UPDATE users SET streak_freeze=streak_freeze-1, last_lesson_date=? WHERE tg_id=?",
            (today, tg_id)
        )
        await conn.commit()
        return {"ok": True, "remaining": (user["streak_freeze"] or 1) - 1}


# ===== WEEKLY LEADERBOARD =====

@app.get("/api/leaderboard/weekly")
async def weekly_leaderboard(tg_id: int):
    from zoneinfo import ZoneInfo
    from datetime import datetime
    today = datetime.now(ZoneInfo("Europe/Kyiv"))
    # Reset weekly XP on Monday
    week_start = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")

    async with aiosqlite.connect(CLOUD_DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        # Reset stale weekly XP
        await conn.execute(
            "UPDATE users SET weekly_xp=0, weekly_reset_date=? WHERE weekly_reset_date IS NULL OR weekly_reset_date < ?",
            (week_start, week_start)
        )
        await conn.commit()

        rows = await (await conn.execute(
            "SELECT tg_id, first_name, username, weekly_xp, streak FROM users ORDER BY weekly_xp DESC LIMIT 10"
        )).fetchall()

        caller = await (await conn.execute(
            "SELECT weekly_xp FROM users WHERE tg_id=?", (tg_id,)
        )).fetchone()

        board = [{"rank": i+1, "tg_id": r["tg_id"], "name": r["first_name"] or r["username"] or "?",
                  "weekly_xp": r["weekly_xp"] or 0, "streak": r["streak"] or 0} for i, r in enumerate(rows)]

        return {"board": board, "my_weekly_xp": caller["weekly_xp"] if caller else 0}


# ===== STATIC FILES =====

# Serve the mini app static files
app.mount("/", StaticFiles(directory=MINI_APP_DIR, html=True), name="static")
