"""
database.py — SQLite async database for ThreeWordsDaily
Uses aiosqlite. DB file: threewords.db
"""

import asyncio
import json
import os
from datetime import date, timedelta
from typing import Optional

import aiosqlite

DB_PATH = os.getenv(
    "DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "miniapp", "threewords.db")
)


# ===== INIT =====

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id INTEGER UNIQUE NOT NULL,
                first_name TEXT DEFAULT '',
                username TEXT DEFAULT '',
                level TEXT DEFAULT 'A2',
                topic TEXT DEFAULT 'everyday',
                xp INTEGER DEFAULT 0,
                streak INTEGER DEFAULT 0,
                last_lesson_date TEXT DEFAULT NULL,
                words_learned TEXT DEFAULT '[]',
                total_lessons INTEGER DEFAULT 0,
                total_quizzes INTEGER DEFAULT 0,
                correct_answers INTEGER DEFAULT 0,
                referrer_id INTEGER DEFAULT NULL,
                referrals_count INTEGER DEFAULT 0,
                registered_at TEXT DEFAULT '',
                pet_stage INTEGER DEFAULT 0,
                pet_mood INTEGER DEFAULT 0,
                pet_hp INTEGER DEFAULT 50,
                pet_xp INTEGER DEFAULT 0,
                streak_freeze INTEGER DEFAULT 0,
                last_login_date TEXT DEFAULT NULL,
                login_streak_day INTEGER DEFAULT 0,
                weekly_xp INTEGER DEFAULT 0,
                weekly_reset_date TEXT DEFAULT NULL
            );

            CREATE TABLE IF NOT EXISTS lessons_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT NOT NULL,
                topic TEXT NOT NULL,
                date TEXT NOT NULL,
                lesson_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(level, topic, date)
            );

            CREATE TABLE IF NOT EXISTS progress_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                xp_earned INTEGER DEFAULT 0,
                data_json TEXT DEFAULT '{}',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS rewards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                badge_id TEXT NOT NULL,
                earned_at TEXT NOT NULL,
                UNIQUE(user_id, badge_id)
            );
        """)
        await db.commit()

        # Auto-migration: add new columns if missing
        for _col, _def in [
            ("pet_character",      "TEXT DEFAULT NULL"),
            ("pet_name",           "TEXT DEFAULT NULL"),
            ("streak_freeze",      "INTEGER DEFAULT 0"),
            ("last_login_date",    "TEXT DEFAULT NULL"),
            ("login_streak_day",   "INTEGER DEFAULT 0"),
            ("weekly_xp",          "INTEGER DEFAULT 0"),
            ("weekly_reset_date",  "TEXT DEFAULT NULL"),
        ]:
            try:
                await db.execute(f"ALTER TABLE users ADD COLUMN {_col} {_def}")
                await db.commit()
            except Exception:
                pass  # column already exists


# ===== USER HELPERS =====

def _row_to_dict(row, cursor) -> dict:
    if row is None:
        return None
    cols = [d[0] for d in cursor.description]
    return dict(zip(cols, row))


async def get_or_create_user(tg_id: int, first_name: str = "", username: str = "") -> dict:
    today = str(date.today())
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE tg_id = ?", (tg_id,)
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            await db.execute(
                """INSERT INTO users
                   (tg_id, first_name, username, registered_at, words_learned)
                   VALUES (?, ?, ?, ?, ?)""",
                (tg_id, first_name, username, today, "[]"),
            )
            await db.commit()
            async with db.execute(
                "SELECT * FROM users WHERE tg_id = ?", (tg_id,)
            ) as cursor:
                row = await cursor.fetchone()
        else:
            # update name if provided
            if first_name:
                await db.execute(
                    "UPDATE users SET first_name=?, username=? WHERE tg_id=?",
                    (first_name, username, tg_id),
                )
                await db.commit()

        return dict(row)


async def get_user(tg_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE tg_id = ?", (tg_id,)
        ) as cursor:
            row = await cursor.fetchone()
        return dict(row) if row else None


async def update_user(tg_id: int, **fields):
    if not fields:
        return
    set_clause = ", ".join(f"{k}=?" for k in fields)
    values = list(fields.values()) + [tg_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE users SET {set_clause} WHERE tg_id=?", values
        )
        await db.commit()


# ===== PROGRESS =====

async def add_progress_event(tg_id: int, event_type: str, xp_earned: int = 0, data: dict = None):
    now = str(date.today())
    data_json = json.dumps(data or {})
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO progress_events (user_id, event_type, xp_earned, data_json, created_at) VALUES (?,?,?,?,?)",
            (tg_id, event_type, xp_earned, data_json, now),
        )
        await db.commit()


# ===== STATS =====

async def get_user_stats(tg_id: int) -> dict:
    user = await get_user(tg_id)
    if not user:
        return {}

    async with aiosqlite.connect(DB_PATH) as db:
        # rank by XP
        async with db.execute(
            "SELECT COUNT(*) FROM users WHERE xp > ?", (user["xp"],)
        ) as cur:
            row = await cur.fetchone()
            rank = (row[0] + 1) if row else 1

    words_list = json.loads(user.get("words_learned") or "[]")
    xp = user.get("xp", 0)

    if xp >= 1000:
        rank_label = "👑 Майстер"
    elif xp >= 500:
        rank_label = "💎 Експерт"
    elif xp >= 200:
        rank_label = "🔥 Практик"
    elif xp >= 50:
        rank_label = "⚡ Учень"
    else:
        rank_label = "🌱 Новачок"

    return {
        "streak": user.get("streak", 0),
        "xp": xp,
        "rank": rank,
        "rank_label": rank_label,
        "level": user.get("level", "A2"),
        "words_learned_count": len(words_list),
        "total_lessons": user.get("total_lessons", 0),
        "total_quizzes": user.get("total_quizzes", 0),
    }


async def get_leaderboard(limit: int = 10) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT tg_id, first_name, xp, streak, words_learned FROM users ORDER BY xp DESC LIMIT ?",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
    result = []
    for i, row in enumerate(rows):
        words_count = len(json.loads(row["words_learned"] or "[]"))
        result.append({
            "rank": i + 1,
            "tg_id": row["tg_id"],
            "first_name": row["first_name"],
            "xp": row["xp"],
            "streak": row["streak"],
            "words_count": words_count,
        })
    return result


# ===== LESSON CACHE =====

async def cache_lesson(level: str, topic: str, lesson_date: str, lesson_json: str):
    now = str(date.today())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR REPLACE INTO lessons_cache
               (level, topic, date, lesson_json, created_at)
               VALUES (?,?,?,?,?)""",
            (level, topic, lesson_date, lesson_json, now),
        )
        await db.commit()


async def get_cached_lesson(level: str, topic: str, lesson_date: str) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT lesson_json FROM lessons_cache WHERE level=? AND topic=? AND date=?",
            (level, topic, lesson_date),
        ) as cursor:
            row = await cursor.fetchone()
    if row:
        try:
            return json.loads(row["lesson_json"])
        except Exception:
            return None
    return None


# ===== REWARDS / BADGES =====

async def add_reward(tg_id: int, badge_id: str) -> bool:
    """Returns True if badge was newly added, False if already existed."""
    now = str(date.today())
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO rewards (user_id, badge_id, earned_at) VALUES (?,?,?)",
                (tg_id, badge_id, now),
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def get_rewards(tg_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT badge_id, earned_at FROM rewards WHERE user_id=? ORDER BY earned_at",
            (tg_id,),
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(r) for r in rows]


# ===== STREAK LOGIC =====

def compute_streak(last_lesson_date: Optional[str], current_streak: int) -> tuple[int, bool]:
    """
    Returns (new_streak, did_update).
    Call this to decide if streak should increase.
    """
    today = str(date.today())
    yesterday = str(date.today() - timedelta(days=1))

    if last_lesson_date == today:
        # Already counted today
        return current_streak, False

    if last_lesson_date == yesterday:
        return current_streak + 1, True
    else:
        return 1, True


# ===== MAIN (for testing) =====

if __name__ == "__main__":
    asyncio.run(init_db())
    print("DB OK")
