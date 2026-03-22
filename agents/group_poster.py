"""
agents/group_poster.py — Post agent reports to Telegram group topics

All bots use this to publish their activity to the internal group.
Calls the group_manager.py API server (http://127.0.0.1:9000/post).
"""

import asyncio
import logging
import aiohttp

log = logging.getLogger("group_poster")

GROUP_API = "http://127.0.0.1:9000/post"


async def post_to_group(agent: str, message: str) -> bool:
    """
    Post a message to the internal group topic for this agent.

    agent: 'analyst' | 'publisher' | 'growth' | 'ops' | 'teacher' |
           'speak' | 'test' | 'agent' | 'deploy' | 'alert'
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                GROUP_API,
                json={"agent": agent, "message": message},
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status == 200:
                    return True
                log.warning("Group API returned %d", resp.status)
                return False
    except Exception as e:
        log.debug("Group API not available: %s", e)  # silent if manager not running
        return False


def post_to_group_sync(agent: str, message: str) -> bool:
    """Sync wrapper for post_to_group."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(post_to_group(agent, message))
            return True
        return loop.run_until_complete(post_to_group(agent, message))
    except Exception:
        return False


# ── Convenience functions per agent ──────────────────────────────────────────

async def analyst_report(text: str) -> None:
    await post_to_group("analyst", text)

async def ops_report(text: str) -> None:
    await post_to_group("ops", text)

async def growth_report(text: str) -> None:
    await post_to_group("growth", text)

async def content_report(text: str) -> None:
    await post_to_group("publisher", text)

async def deploy_report(text: str) -> None:
    await post_to_group("deploy", text)

async def alert(text: str) -> None:
    await post_to_group("alert", text)

async def agent_discussion(text: str) -> None:
    await post_to_group("agent", text)
