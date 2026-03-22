"""
group_manager.py — Voodoo Internal Group Manager

Uses Telethon user account to:
1. Join the internal coordination group
2. Create topics for each agent/bot
3. Post agent activity to correct topics
4. Enable autonomous agent coordination via topics

Group: https://t.me/+h25oRixdZco3ZWQy  (My team)

Topics structure:
  General       — загальні оголошення
  Analysis      — VoodooAnalystBot звіти
  Content       — VoodooPublisherBot контент
  Growth        — VoodooGrowthBot активність
  Ops           — VoodooOpsBot операції
  Teaching      — VoodooTeacherBot сесії
  Speaking      — VoodooSpeakBot активність
  Testing       — VoodooTesttbot результати
  Agent-Talk    — Claude Agent SDK внутрішні дискусії
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.functions.channels import (
    CreateForumTopicRequest,
    GetForumTopicsRequest,
)
from telethon.tl.functions.messages import ImportChatInviteRequest

load_dotenv()

logging.basicConfig(
    format="%(asctime)s [group_mgr] %(levelname)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("group_mgr")

# Telethon credentials (from .env)
API_ID   = int(os.getenv("TELETHON_API_ID", "0"))
API_HASH = os.getenv("TELETHON_API_HASH", "")
SESSION  = os.getenv("TELETHON_SESSION", "voodoo_manager")

# Internal group
INTERNAL_GROUP_LINK = "https://t.me/+h25oRixdZco3ZWQy"
INTERNAL_GROUP_HASH = "h25oRixdZco3ZWQy"

# State file to track topic IDs
STATE_FILE = Path(__file__).parent / "group_state.json"

# Required topics
TOPICS = [
    {"name": "📊 Analysis",     "icon": "5309880029584408379"},  # chart emoji
    {"name": "📢 Content",      "icon": "5309880029584408379"},
    {"name": "📈 Growth",       "icon": "5309880029584408379"},
    {"name": "🛡 Ops",          "icon": "5309880029584408379"},
    {"name": "📚 Teaching",     "icon": "5309880029584408379"},
    {"name": "🔊 Speaking",     "icon": "5309880029584408379"},
    {"name": "🧪 Testing",      "icon": "5309880029584408379"},
    {"name": "🤖 Agent-Talk",   "icon": "5309880029584408379"},
    {"name": "🚀 Deployments",  "icon": "5309880029584408379"},
    {"name": "⚠️ Alerts",       "icon": "5309880029584408379"},
]


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


async def get_or_create_topics(client: TelegramClient, group) -> dict:
    """Create missing topics, return name→topic_id mapping."""
    state = load_state()
    topic_ids = state.get("topic_ids", {})

    try:
        # Get existing topics
        result = await client(GetForumTopicsRequest(
            channel=group, offset_date=0, offset_id=0,
            offset_topic=0, limit=100,
        ))
        existing = {t.title: t.id for t in result.topics}
        log.info("Existing topics: %s", list(existing.keys()))
    except Exception as e:
        log.warning("Could not fetch topics: %s", e)
        existing = {}

    # Create missing topics
    for topic_cfg in TOPICS:
        name = topic_cfg["name"]
        if name in existing:
            topic_ids[name] = existing[name]
            log.info("Topic exists: %s (id=%d)", name, existing[name])
            continue

        try:
            result = await client(CreateForumTopicRequest(
                channel=group,
                title=name,
                random_id=int(datetime.now().timestamp() * 1000),
            ))
            tid = result.updates[0].id if result.updates else 0
            topic_ids[name] = tid
            log.info("✅ Created topic: %s (id=%d)", name, tid)
            await asyncio.sleep(1)  # rate limit
        except Exception as e:
            log.error("Failed to create topic %s: %s", name, e)

    state["topic_ids"] = topic_ids
    save_state(state)
    return topic_ids


async def post_to_topic(client, group, topic_id: int, text: str) -> None:
    """Post a message to a specific forum topic."""
    try:
        await client.send_message(
            entity=group,
            message=text,
            reply_to=topic_id,
            parse_mode="html",
        )
    except Exception as e:
        log.error("Failed to post to topic %d: %s", topic_id, e)


async def post_agent_report(
    client: TelegramClient,
    group,
    topic_ids: dict,
    agent: str,
    message: str,
) -> None:
    """Post an agent's report to its designated topic."""
    topic_map = {
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
    topic_name = topic_map.get(agent, "📊 Analysis")
    topic_id   = topic_ids.get(topic_name, 0)

    if not topic_id:
        log.warning("No topic_id for %s", topic_name)
        return

    now = datetime.now().strftime("%d.%m %H:%M")
    full_text = f"<b>[{agent.upper()} — {now}]</b>\n\n{message}"
    await post_to_topic(client, group, topic_id, full_text)


# ── HTTP API for bots to call ─────────────────────────────────────────────────
# Bots will POST to this local server to publish to topics

async def start_api_server(client, group, topic_ids: dict) -> None:
    """Minimal HTTP server so bots can post to group topics via localhost."""
    from aiohttp import web

    async def handle_post(request):
        try:
            data = await request.json()
            agent   = data.get("agent", "analyst")
            message = data.get("message", "")
            await post_agent_report(client, group, topic_ids, agent, message)
            return web.json_response({"ok": True})
        except Exception as e:
            return web.json_response({"ok": False, "error": str(e)}, status=500)

    async def handle_status(request):
        return web.json_response({
            "topics": topic_ids,
            "status": "running",
        })

    app = web.Application()
    app.router.add_post("/post", handle_post)
    app.router.add_get("/status", handle_status)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 9000)
    await site.start()
    log.info("Group API server started at http://127.0.0.1:9000")


async def main():
    if not API_ID or not API_HASH:
        print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  Telethon credentials not set in .env

Add to VoodooBot/.env:
  TELETHON_API_ID=<your api_id>
  TELETHON_API_HASH=<your api_hash>

Get them at: https://my.telegram.org/apps
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
        return

    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.start()
    log.info("Telethon client started")

    # Join the internal group if not already member
    state = load_state()
    group = None

    if "group_id" in state:
        try:
            group = await client.get_entity(state["group_id"])
            log.info("Using cached group id: %s", state["group_id"])
        except Exception:
            group = None

    if not group:
        try:
            result = await client(ImportChatInviteRequest(INTERNAL_GROUP_HASH))
            group = result.chats[0]
            state["group_id"] = group.id
            save_state(state)
            log.info("✅ Joined group: %s (id=%d)", group.title, group.id)
        except Exception as e:
            if "already" in str(e).lower():
                # Already a member — find by link
                async for dialog in client.iter_dialogs():
                    if hasattr(dialog.entity, 'username') or 'team' in (dialog.name or '').lower():
                        log.info("Found: %s", dialog.name)
                group = await client.get_entity(INTERNAL_GROUP_HASH)
                state["group_id"] = group.id
                save_state(state)
            else:
                log.error("Join failed: %s", e)
                return

    log.info("Group: %s", getattr(group, 'title', 'Unknown'))

    # Create topics
    topic_ids = await get_or_create_topics(client, group)
    log.info("Topics ready: %d", len(topic_ids))

    # Post startup announcement to Ops topic
    await post_agent_report(
        client, group, topic_ids, "ops",
        f"🚀 <b>Voodoo Platform запущена</b>\n\n"
        f"Всі агенти онлайн. Топіки створені.\n"
        f"Звіти агентів будуть з'являтися в відповідних топіках.\n\n"
        f"<code>{datetime.now().strftime('%d.%m.%Y %H:%M')}</code>"
    )

    # Start API server for bots to post
    await start_api_server(client, group, topic_ids)

    log.info("✅ Group Manager running — listening on http://127.0.0.1:9000")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
