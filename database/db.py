"""
database/db.py — Voodoo Platform SQLite Database Layer

Single source of truth for all bots. Thread-safe async wrapper.
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any

DB_PATH = Path(os.getenv("DB_PATH", Path(__file__).parent / "voodoo.db"))


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=20, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create all tables. Safe to call on every startup."""
    conn = _connect()
    conn.executescript("""
    -- ── USERS ─────────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS users (
        tg_id               INTEGER PRIMARY KEY,
        username            TEXT    DEFAULT '',
        first_name          TEXT    DEFAULT '',
        language_code       TEXT    DEFAULT 'uk',
        level               TEXT    DEFAULT '',
        xp                  INTEGER DEFAULT 0,
        streak              INTEGER DEFAULT 0,
        lives               INTEGER DEFAULT 5,
        league              TEXT    DEFAULT 'bronze',
        total_lessons       INTEGER DEFAULT 0,
        total_words         INTEGER DEFAULT 0,
        correct_answers     INTEGER DEFAULT 0,
        wrong_answers       INTEGER DEFAULT 0,
        last_lesson_date    TEXT    DEFAULT '',
        last_active         TEXT    DEFAULT '',
        login_streak_day    INTEGER DEFAULT 0,
        last_login_date     TEXT    DEFAULT '',
        weekly_xp           INTEGER DEFAULT 0,
        weekly_reset_date   TEXT    DEFAULT '',
        streak_freeze       INTEGER DEFAULT 0,
        is_premium          INTEGER DEFAULT 0,
        premium_expires     TEXT    DEFAULT '',
        stars_spent         INTEGER DEFAULT 0,
        referrer_id         INTEGER DEFAULT 0,
        referral_count      INTEGER DEFAULT 0,
        pet_character       TEXT    DEFAULT '',
        pet_name            TEXT    DEFAULT '',
        pet_archetype       TEXT    DEFAULT '',
        hp                  INTEGER DEFAULT 100,
        source_bot          TEXT    DEFAULT 'voodoo_bot',
        registered_at       TEXT    DEFAULT (date('now'))
    );

    -- ── WORDS ─────────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS words (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        word        TEXT NOT NULL,
        translation TEXT NOT NULL,
        ipa         TEXT DEFAULT '',
        level       TEXT DEFAULT 'A2',
        theme       TEXT DEFAULT '',
        example_en  TEXT DEFAULT '',
        example_ua  TEXT DEFAULT '',
        audio_url   TEXT DEFAULT '',
        created_at  TEXT DEFAULT (date('now'))
    );

    -- ── USER WORDS (learned tracking) ─────────────────────────────
    CREATE TABLE IF NOT EXISTS user_words (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        tg_id       INTEGER NOT NULL,
        word_id     INTEGER NOT NULL,
        correct     INTEGER DEFAULT 0,
        wrong       INTEGER DEFAULT 0,
        last_seen   TEXT    DEFAULT (date('now')),
        UNIQUE(tg_id, word_id),
        FOREIGN KEY (tg_id) REFERENCES users(tg_id),
        FOREIGN KEY (word_id) REFERENCES words(id)
    );

    -- ── CONTENT PLAN ──────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS content_plan (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        scheduled_at    TEXT NOT NULL,
        content_type    TEXT DEFAULT 'word',
        topic           TEXT DEFAULT '',
        theme           TEXT DEFAULT '',
        post_text       TEXT DEFAULT '',
        status          TEXT DEFAULT 'pending',
        posted_at       TEXT DEFAULT '',
        channel_msg_id  INTEGER DEFAULT 0
    );

    -- ── CONTENT METRICS ──────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS content_metrics (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id         INTEGER,
        date            TEXT DEFAULT (date('now')),
        views           INTEGER DEFAULT 0,
        reactions       INTEGER DEFAULT 0,
        comments        INTEGER DEFAULT 0,
        shares          INTEGER DEFAULT 0,
        ctr             REAL    DEFAULT 0,
        FOREIGN KEY (post_id) REFERENCES content_plan(id)
    );

    -- ── AGENT TASKS ───────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS agent_tasks (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_name  TEXT NOT NULL,
        task_type   TEXT NOT NULL,
        payload     TEXT DEFAULT '{}',
        status      TEXT DEFAULT 'pending',
        result      TEXT DEFAULT '',
        created_at  TEXT DEFAULT (datetime('now')),
        updated_at  TEXT DEFAULT (datetime('now'))
    );

    -- ── OPS LOG ───────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS ops_log (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        actor       TEXT DEFAULT 'system',
        action      TEXT NOT NULL,
        target      TEXT DEFAULT '',
        detail      TEXT DEFAULT '',
        ts          TEXT DEFAULT (datetime('now'))
    );

    -- ── APPROVALS ─────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS approvals (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        request_by  TEXT NOT NULL,
        action_type TEXT NOT NULL,
        payload     TEXT DEFAULT '{}',
        status      TEXT DEFAULT 'pending',
        reviewed_by TEXT DEFAULT '',
        reviewed_at TEXT DEFAULT '',
        created_at  TEXT DEFAULT (datetime('now'))
    );
    """)
    conn.commit()
    conn.close()


# ── Async helpers ─────────────────────────────────────────────────────────────

async def _run(fn, *args) -> Any:
    """Run a synchronous DB function in a thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, fn, *args)


def _get_user_sync(tg_id: int, first_name: str = "", username: str = "") -> dict:
    conn = _connect()
    row = conn.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,)).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO users (tg_id, first_name, username, last_active) VALUES (?,?,?,?)",
            (tg_id, first_name, username, str(date.today()))
        )
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,)).fetchone()
    conn.close()
    return dict(row) if row else {}


async def get_user(tg_id: int, first_name: str = "", username: str = "") -> dict:
    return await _run(_get_user_sync, tg_id, first_name, username)


def _update_user_sync(tg_id: int, **kwargs) -> None:
    if not kwargs:
        return
    cols = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [tg_id]
    conn = _connect()
    conn.execute(f"UPDATE users SET {cols} WHERE tg_id=?", vals)
    conn.commit()
    conn.close()


async def update_user(tg_id: int, **kwargs) -> None:
    await _run(_update_user_sync, tg_id, **kwargs)


def _get_stats_sync() -> dict:
    conn = _connect()
    today = str(date.today())
    from datetime import timedelta
    week_ago = str(date.today() - timedelta(days=7))
    month_ago = str(date.today() - timedelta(days=30))

    total       = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    active_today = conn.execute("SELECT COUNT(*) FROM users WHERE last_lesson_date=?", (today,)).fetchone()[0]
    active_week  = conn.execute("SELECT COUNT(*) FROM users WHERE last_lesson_date>=?", (week_ago,)).fetchone()[0]
    active_month = conn.execute("SELECT COUNT(*) FROM users WHERE last_lesson_date>=?", (month_ago,)).fetchone()[0]
    new_today    = conn.execute("SELECT COUNT(*) FROM users WHERE registered_at=?", (today,)).fetchone()[0]
    new_week     = conn.execute("SELECT COUNT(*) FROM users WHERE registered_at>=?", (week_ago,)).fetchone()[0]
    avg_xp       = conn.execute("SELECT AVG(xp) FROM users").fetchone()[0] or 0
    avg_streak   = conn.execute("SELECT AVG(streak) FROM users").fetchone()[0] or 0
    top10        = conn.execute(
        "SELECT first_name, xp, streak FROM users ORDER BY xp DESC LIMIT 10"
    ).fetchall()
    conn.close()

    return {
        "total_users": total,
        "active_today": active_today,
        "active_week": active_week,
        "active_month": active_month,
        "new_today": new_today,
        "new_week": new_week,
        "avg_xp": round(avg_xp, 1),
        "avg_streak": round(avg_streak, 1),
        "top10": [dict(r) for r in top10],
    }


async def get_stats() -> dict:
    return await _run(_get_stats_sync)


def _log_ops_sync(actor: str, action: str, target: str = "", detail: str = "") -> None:
    conn = _connect()
    conn.execute(
        "INSERT INTO ops_log (actor, action, target, detail) VALUES (?,?,?,?)",
        (actor, action, target, detail)
    )
    conn.commit()
    conn.close()


async def log_ops(actor: str, action: str, target: str = "", detail: str = "") -> None:
    await _run(_log_ops_sync, actor, action, target, detail)


def _create_approval_sync(request_by: str, action_type: str, payload: str) -> int:
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO approvals (request_by, action_type, payload) VALUES (?,?,?)",
        (request_by, action_type, payload)
    )
    approval_id = cur.lastrowid
    conn.commit()
    conn.close()
    return approval_id


async def create_approval(request_by: str, action_type: str, payload: str) -> int:
    return await _run(_create_approval_sync, request_by, action_type, payload)


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
