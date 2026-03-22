"""
agents/group_poster.py — Post agent reports to admin chat (direct) + group topics (if available)

Primary:  direct message to admin via VoodooOpsBot
Fallback: group_manager API on :9000 (if running)
"""

import asyncio
import logging
import os

import aiohttp
from dotenv import load_dotenv

load_dotenv()

log        = logging.getLogger("group_poster")
GROUP_API  = "http://127.0.0.1:9000/post"
OPS_TOKEN  = os.getenv("VOODOO_OPS_BOT_TOKEN", "")
ADMIN_ID   = int(os.getenv("ADMIN_CHAT_ID", "0"))

AGENT_EMOJI = {
    "analyst":   "📊",
    "publisher": "📢",
    "growth":    "📈",
    "ops":       "🛡",
    "teacher":   "📚",
    "speak":     "🔊",
    "test":      "🧪",
    "agent":     "🤖",
    "deploy":    "🚀",
    "alert":     "⚠️",
}


async def _send_to_admin(agent: str, message: str) -> bool:
    """Send directly to admin via OpsBot."""
    if not OPS_TOKEN or not ADMIN_ID:
        return False
    emoji = AGENT_EMOJI.get(agent, "🤖")
    text  = f"{emoji} <b>[{agent.upper()}]</b>\n\n{message}"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                f"https://api.telegram.org/bot{OPS_TOKEN}/sendMessage",
                json={"chat_id": ADMIN_ID, "text": text[:4096], "parse_mode": "HTML"},
                timeout=aiohttp.ClientTimeout(total=8),
            ) as r:
                data = await r.json()
                return data.get("ok", False)
    except Exception as e:
        log.debug("Admin send failed: %s", e)
        return False


async def _send_to_group_api(agent: str, message: str) -> bool:
    """Post to group topics via local group_manager API."""
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                GROUP_API,
                json={"agent": agent, "message": message},
                timeout=aiohttp.ClientTimeout(total=5),
            ) as r:
                return r.status == 200
    except Exception:
        return False


async def post_to_group(agent: str, message: str) -> bool:
    """Post to group topic (if running) AND admin chat."""
    await _send_to_group_api(agent, message)   # silent fail if not running
    return await _send_to_admin(agent, message)


def post_to_group_sync(agent: str, message: str) -> bool:
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(post_to_group(agent, message))
            return True
        return loop.run_until_complete(post_to_group(agent, message))
    except Exception:
        return False


# ── Convenience functions ─────────────────────────────────────────────────────

async def analyst_report(text: str)  -> None: await post_to_group("analyst",   text)
async def ops_report(text: str)      -> None: await post_to_group("ops",       text)
async def growth_report(text: str)   -> None: await post_to_group("growth",    text)
async def content_report(text: str)  -> None: await post_to_group("publisher", text)
async def deploy_report(text: str)   -> None: await post_to_group("deploy",    text)
async def alert(text: str)           -> None: await post_to_group("alert",     text)
async def agent_discussion(text: str)-> None: await post_to_group("agent",     text)
