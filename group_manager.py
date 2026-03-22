"""
group_manager.py — Voodoo Internal Group Manager (Bot API)

No Telethon needed. Uses VoodooOpsBot to manage forum topics.

Setup (one-time):
  1. Add @VoodooOpsBot to "My team" group as ADMIN (Manage Topics permission)
  2. Send any message in the group so the bot sees it
  3. python3 group_manager.py --get-id   ← shows group ID
  4. Set INTERNAL_GROUP_ID=<id> in .env
  5. python3 group_manager.py            ← runs normally

Topics:
  📊 Analysis | 📢 Content | 📈 Growth | 🛡 Ops | 📚 Teaching
  🔊 Speaking | 🧪 Testing | 🤖 Agent-Talk | 🚀 Deployments | ⚠️ Alerts
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import aiohttp
from aiohttp import web
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format="%(asctime)s [group_mgr] %(levelname)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("group_mgr")

BOT_TOKEN        = os.getenv("VOODOO_OPS_BOT_TOKEN", "")
INTERNAL_GROUP_ID = int(os.getenv("INTERNAL_GROUP_ID", "0"))
STATE_FILE       = Path(__file__).parent / "group_state.json"
API_BASE         = f"https://api.telegram.org/bot{BOT_TOKEN}"

TOPICS = [
    "📊 Analysis",
    "📢 Content",
    "📈 Growth",
    "🛡 Ops",
    "📚 Teaching",
    "🔊 Speaking",
    "🧪 Testing",
    "🤖 Agent-Talk",
    "🚀 Deployments",
    "⚠️ Alerts",
]

AGENT_TOPIC_MAP = {
    "analyst":   "📊 Analysis",
    "publisher": "📢 Content",
    "growth":    "📈 Growth",
    "ops":       "🛡 Ops",
    "teacher":   "📚 Teaching",
    "speak":     "🔊 Speaking",
    "test":      "🧪 Testing",
    "agent":     "🤖 Agent-Talk",
    "deploy":    "🚀 Deployments",
    "alert":     "⚠️ Alerts",
}


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


async def tg(session: aiohttp.ClientSession, method: str, **params) -> dict:
    async with session.post(f"{API_BASE}/{method}", json=params) as r:
        return await r.json()


async def get_group_id() -> None:
    """--get-id mode: show recent group IDs."""
    async with aiohttp.ClientSession() as session:
        data = await tg(session, "getUpdates", limit=50, timeout=10)
        chats = {}
        for u in data.get("result", []):
            msg = u.get("message") or u.get("channel_post") or {}
            chat = msg.get("chat", {})
            if chat.get("type") in ("group", "supergroup"):
                chats[chat["id"]] = chat.get("title", "?")

        if not chats:
            print("\n⚠️  Груп не знайдено. Перевір:")
            print("  1. @VoodooOpsBot доданий в групу як адмін")
            print("  2. В групі є хоча б одне повідомлення після додавання бота")
            print("  3. Надішли /start або будь-яке повідомлення в групу\n")
        else:
            print("\n📋 Знайдені групи:")
            for gid, title in chats.items():
                print(f"  {title}: {gid}")
            print("\nДодай в .env:  INTERNAL_GROUP_ID=<id>\n")


async def create_topic(session: aiohttp.ClientSession, group_id: int, name: str) -> int:
    r = await tg(session, "createForumTopic", chat_id=group_id, name=name)
    if r.get("ok"):
        tid = r["result"]["message_thread_id"]
        log.info("✅ Created topic: %s (id=%d)", name, tid)
        return tid
    log.error("Failed to create topic %s: %s", name, r.get("description"))
    return 0


async def post_to_topic(
    session: aiohttp.ClientSession,
    group_id: int,
    thread_id: int,
    text: str,
) -> bool:
    r = await tg(
        session, "sendMessage",
        chat_id=group_id,
        message_thread_id=thread_id,
        text=text,
        parse_mode="HTML",
    )
    return r.get("ok", False)


async def setup_topics(session: aiohttp.ClientSession, group_id: int) -> dict:
    """Create missing topics, return name→thread_id mapping."""
    state = load_state()
    topic_ids: dict = state.get("topic_ids", {})

    for name in TOPICS:
        if name in topic_ids:
            log.info("Topic exists: %s (id=%d)", name, topic_ids[name])
            continue
        tid = await create_topic(session, group_id, name)
        if tid:
            topic_ids[name] = tid
        await asyncio.sleep(0.5)

    state["topic_ids"] = topic_ids
    save_state(state)
    return topic_ids


async def post_agent_report(
    session: aiohttp.ClientSession,
    topic_ids: dict,
    agent: str,
    message: str,
) -> None:
    topic_name = AGENT_TOPIC_MAP.get(agent, "🤖 Agent-Talk")
    thread_id  = topic_ids.get(topic_name, 0)
    if not thread_id:
        log.warning("No thread_id for agent=%s topic=%s", agent, topic_name)
        return
    now  = datetime.now().strftime("%d.%m %H:%M")
    text = f"<b>[{agent.upper()} — {now}]</b>\n\n{message}"
    ok   = await post_to_topic(session, INTERNAL_GROUP_ID, thread_id, text)
    if ok:
        log.info("Posted to %s", topic_name)


# ── HTTP API server ────────────────────────────────────────────────────────────

def _kill_port(port: int) -> None:
    """Kill any process holding the given port (cleanup before bind)."""
    import subprocess
    r = subprocess.run(["lsof", "-ti", f":{port}"], capture_output=True, text=True)
    for pid in r.stdout.strip().split():
        if pid.isdigit():
            subprocess.run(["kill", "-9", pid], capture_output=True)
            log.info("Killed PID %s holding port %d", pid, port)


async def start_api_server(topic_ids: dict) -> None:
    _kill_port(9000)
    await asyncio.sleep(0.5)

    async with aiohttp.ClientSession() as session:

        async def handle_post(request: web.Request) -> web.Response:
            try:
                data    = await request.json()
                agent   = data.get("agent", "agent")
                message = data.get("message", "")
                await post_agent_report(session, topic_ids, agent, message)
                return web.json_response({"ok": True})
            except Exception as e:
                return web.json_response({"ok": False, "error": str(e)}, status=500)

        async def handle_status(request: web.Request) -> web.Response:
            return web.json_response({"topics": topic_ids, "status": "running"})

        app = web.Application()
        app.router.add_post("/post",    handle_post)
        app.router.add_get("/status",   handle_status)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 9000)
        await site.start()
        log.info("API server on http://127.0.0.1:9000")

        # Keep running
        while True:
            await asyncio.sleep(3600)


async def main() -> None:
    if not BOT_TOKEN:
        print("❌ VOODOO_OPS_BOT_TOKEN not set in .env")
        return

    if not INTERNAL_GROUP_ID:
        print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  INTERNAL_GROUP_ID не встановлено

Кроки:
  1. Додай @VoodooOpsBot в групу "My team" як АДМІН
  2. Дай право: Manage Topics
  3. Надішли будь-яке повідомлення в групу
  4. Запусти: python3 group_manager.py --get-id
  5. Скопіюй ID в .env: INTERNAL_GROUP_ID=<id>
  6. Запусти знову: python3 group_manager.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
        return

    async with aiohttp.ClientSession() as session:
        log.info("Setting up topics in group %d...", INTERNAL_GROUP_ID)
        topic_ids = await setup_topics(session, INTERNAL_GROUP_ID)
        log.info("Topics ready: %d", len(topic_ids))

        # Startup announcement — send only once per day (guard against crash-loop restarts)
        state = load_state()
        today = datetime.now().strftime("%Y-%m-%d")
        if state.get("last_startup_notified") != today:
            await post_agent_report(
                session, topic_ids, "ops",
                "🚀 <b>Voodoo Platform запущена</b>\n\n"
                "Всі агенти онлайн. Топіки створені.\n"
                f"<code>{datetime.now().strftime('%d.%m.%Y %H:%M')}</code>"
            )
            state["last_startup_notified"] = today
            save_state(state)

    log.info("Starting API server...")
    await start_api_server(topic_ids)


if __name__ == "__main__":
    if "--get-id" in sys.argv:
        asyncio.run(get_group_id())
    else:
        asyncio.run(main())
