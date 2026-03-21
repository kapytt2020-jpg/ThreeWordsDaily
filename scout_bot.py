"""
scout_bot.py — Growth Agent / Student Finder

Monitors configured Telegram groups for trigger phrases indicating
someone wants to learn English. Replies organically (once per user per group)
with a helpful recommendation.

Rate limited: max 3 organic replies per hour, 1 reply per user per group ever.
Only operates in explicitly whitelisted groups.

Run via LaunchAgent: com.threewordsdaily.scout.plist
Uses: telethon (user account) + python-telegram-bot (for sending replies via bot)
"""

import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format="%(asctime)s [scout] %(levelname)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("scout")

# ── Config ──────────────────────────────────────────────────────────────────
BOT_USERNAME    = os.getenv("LEARNING_BOT_USERNAME", "ThreeWordsDailyBot")
GROUP_INVITE    = os.getenv("TELEGRAM_CHAT_INVITE", "")   # e.g. t.me/+xxxxx
SCOUT_SESSION   = os.getenv("SCOUT_SESSION", "scout_session")
SCOUT_API_ID    = os.getenv("SCOUT_API_ID", "")
SCOUT_API_HASH  = os.getenv("SCOUT_API_HASH", "")

# Groups to monitor (add public group usernames here, no @)
# Admin sets these in .env as comma-separated list
WATCH_GROUPS_RAW = os.getenv("SCOUT_WATCH_GROUPS", "")
WATCH_GROUPS = [g.strip().lstrip("@") for g in WATCH_GROUPS_RAW.split(",") if g.strip()]

# Rate limiting
MAX_REPLIES_PER_HOUR = 3
COOLDOWN_SECONDS     = 3600 // MAX_REPLIES_PER_HOUR   # 20 min between replies

# State file (tracks who we already replied to)
STATE_FILE = Path(os.path.dirname(os.path.abspath(__file__))) / "scout_state.json"

# ── Trigger phrases (Ukrainian + English) ───────────────────────────────────
TRIGGERS = [
    # Ukrainian
    r"хочу вчити англійськ",
    r"хочу учити англійськ",
    r"порадьте (бот|апп|додаток).{0,20}англ",
    r"як вчити англійськ",
    r"де вчити англійськ",
    r"вивчаю англійськ",
    r"вчу англійськ",
    r"хочу підтягнути англійськ",
    r"англійська (для|початківц)",
    r"вчити (english|англійськ).{0,20}(бот|телеграм)",
    r"порадьте (щось|ресурс).{0,20}(мов|англ)",
    r"де (можна|можно) вивчити англійськ",
    # English
    r"want to learn english",
    r"learning english",
    r"english (bot|app).{0,10}(recommend|advice|suggest)",
    r"telegram.*english.*learn",
    r"best.*english.*telegram",
    r"how to improve.*english",
]

TRIGGER_RE = re.compile("|".join(TRIGGERS), re.IGNORECASE)

# ── Reply templates (rotated to avoid looking like spam) ────────────────────
REPLIES = [
    "👋 Спробуй @{bot} — навчаєш 3 нових слова щодня + тамагочі-пет який росте разом з тобою 🐾 Є лідерборд, квізи і безкоштовно!",
    "📚 @{bot} — кожен день 3 слова + маленький урок, пет який сумує якщо не вчишся 😅 Спробуй, це безкоштовно!",
    "Зацікавить @{bot} — вивчаєш англійські слова щодня, а ще є свій цифровий пет 🐾 Група: {group}",
    "💡 Якщо шукаєш щось цікаве — @{bot} дає 3 слова на день + квіз + тамагочі. Безкоштовно, є лідерборд!",
]

# ── State management ─────────────────────────────────────────────────────────
def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"replied": {}, "hourly_count": 0, "hour_start": time.time()}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def can_reply(state: dict, group: str, user_id: int) -> bool:
    """Check rate limits and dedup."""
    # Reset hourly counter
    if time.time() - state.get("hour_start", 0) > 3600:
        state["hourly_count"] = 0
        state["hour_start"] = time.time()

    if state.get("hourly_count", 0) >= MAX_REPLIES_PER_HOUR:
        return False

    key = f"{group}:{user_id}"
    if key in state.get("replied", {}):
        return False

    return True


def mark_replied(state: dict, group: str, user_id: int) -> None:
    state.setdefault("replied", {})[f"{group}:{user_id}"] = datetime.now().isoformat()
    state["hourly_count"] = state.get("hourly_count", 0) + 1
    save_state(state)


# ── Main monitor loop ────────────────────────────────────────────────────────
async def run_monitor():
    if not SCOUT_API_ID or not SCOUT_API_HASH:
        log.error("SCOUT_API_ID / SCOUT_API_HASH not set in .env — cannot start scout")
        log.info("Get them at https://my.telegram.org/apps")
        return

    if not WATCH_GROUPS:
        log.warning("SCOUT_WATCH_GROUPS not set — nothing to monitor")
        return

    try:
        from telethon import TelegramClient, events
        from telethon.tl.types import MessageEntityMention
    except ImportError:
        log.error("telethon not installed. Run: pip install telethon")
        return

    client = TelegramClient(SCOUT_SESSION, int(SCOUT_API_ID), SCOUT_API_HASH)
    state = load_state()

    reply_idx = [0]

    @client.on(events.NewMessage(chats=WATCH_GROUPS))
    async def handler(event):
        msg = event.message
        if not msg or not msg.text:
            return

        # Only reply to messages with trigger phrases
        if not TRIGGER_RE.search(msg.text):
            return

        sender = await event.get_sender()
        if not sender or getattr(sender, "bot", False):
            return

        group = str(event.chat_id)

        if not can_reply(state, group, sender.id):
            log.info("Rate limited or already replied to %s in %s", sender.id, group)
            return

        # Pick next reply template (rotate)
        template = REPLIES[reply_idx[0] % len(REPLIES)]
        reply_idx[0] += 1

        text = template.format(
            bot=BOT_USERNAME,
            group=GROUP_INVITE or f"t.me/{BOT_USERNAME}"
        )

        try:
            await asyncio.sleep(2 + reply_idx[0] % 3)  # natural delay
            await event.reply(text)
            mark_replied(state, group, sender.id)
            log.info("✅ Replied to %s (@%s) in group %s",
                     sender.id, getattr(sender, "username", "?"), group)
        except Exception as exc:
            log.error("Reply failed: %s", exc)

    log.info("Scout starting — monitoring %d groups", len(WATCH_GROUPS))
    log.info("Groups: %s", WATCH_GROUPS)

    await client.start()
    await client.run_until_disconnected()


async def main():
    await run_monitor()


if __name__ == "__main__":
    asyncio.run(main())
