"""
agents/interbot_bus.py — Voodoo Inter-Bot Communication Bus

Every bot in the platform can:
  - SEND a request to another bot via the group topic
  - LISTEN and RESPOND to requests directed at it

Message format in group topic:
  [BUS] from:scheduler to:teacher action:get_word {"level":"B2"}

Each bot registers handlers for its own actions.
The bus monitors the group topic and routes accordingly.

Usage in a bot:
    from agents.interbot_bus import BusClient
    bus = BusClient("scheduler", BOT_TOKEN, GROUP_ID, BUS_TOPIC_ID)
    await bus.send("teacher", "get_word", {"level": "B2"})

    @bus.on("get_word")
    async def handle_get_word(data, reply):
        word = pick_word(data["level"])
        await reply({"word": word})
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from typing import Any, Awaitable, Callable

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("interbot_bus")

# ── Constants ─────────────────────────────────────────────────────────────────

BUS_PREFIX     = "[BUS]"
# Group + topic where all bots communicate
GROUP_ID       = int(os.getenv("INTERNAL_GROUP_ID", "0"))
BUS_TOPIC_ID   = int(os.getenv("BUS_TOPIC_ID", "0"))   # set in .env after creating topic
POLL_INTERVAL  = 5   # seconds between polling for new messages
MSG_TTL        = 120  # ignore messages older than 2 minutes

# Pattern: [BUS] from:X to:Y action:Z {json}
_BUS_RE = re.compile(
    r"\[BUS\]\s+from:(\S+)\s+to:(\S+)\s+action:(\S+)(?:\s+(\{.*\}))?\s*$",
    re.DOTALL,
)

Handler = Callable[[dict, Callable[[dict], Awaitable[None]]], Awaitable[None]]


class BusClient:
    """Lightweight inter-bot message bus using a Telegram group topic."""

    def __init__(
        self,
        bot_name: str,
        token: str,
        group_id: int = GROUP_ID,
        topic_id: int = BUS_TOPIC_ID,
    ):
        self.name     = bot_name
        self.token    = token
        self.group_id = group_id
        self.topic_id = topic_id
        self._handlers: dict[str, Handler] = {}
        self._last_update_id = 0
        self._running = False

    # ── Registration ──────────────────────────────────────────────────────────

    def on(self, action: str):
        """Decorator: register a handler for an action directed at this bot."""
        def decorator(fn: Handler):
            self._handlers[action] = fn
            return fn
        return decorator

    # ── Sending ───────────────────────────────────────────────────────────────

    async def send(self, to: str, action: str, data: dict | None = None) -> None:
        """Post a request to the bus topic."""
        payload = json.dumps(data or {})
        text = f"{BUS_PREFIX} from:{self.name} to:{to} action:{action} {payload}"
        await self._post_message(text)

    async def _reply(self, to: str, action: str, data: dict) -> None:
        payload = json.dumps(data)
        text = f"{BUS_PREFIX} from:{self.name} to:{to} action:{action}_reply {payload}"
        await self._post_message(text)

    async def _post_message(self, text: str) -> None:
        import httpx
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        params: dict[str, Any] = {
            "chat_id": self.group_id,
            "text": text,
        }
        if self.topic_id:
            params["message_thread_id"] = self.topic_id
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(url, json=params)
        except Exception as e:
            log.warning("Bus send failed: %s", e)

    # ── Listening ─────────────────────────────────────────────────────────────

    async def listen(self) -> None:
        """Poll for messages and dispatch to handlers. Call this in your bot's startup."""
        self._running = True
        log.info("[%s] Bus listener started (group=%s topic=%s)", self.name, self.group_id, self.topic_id)
        while self._running:
            try:
                await self._poll_once()
            except Exception as e:
                log.warning("[%s] Bus poll error: %s", self.name, e)
            await asyncio.sleep(POLL_INTERVAL)

    async def _poll_once(self) -> None:
        import httpx
        url = f"https://api.telegram.org/bot{self.token}/getUpdates"
        params = {
            "offset": self._last_update_id + 1,
            "timeout": 3,
            "allowed_updates": ["message"],
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params=params)
        if resp.status_code != 200:
            return
        data = resp.json()
        for upd in data.get("result", []):
            self._last_update_id = upd["update_id"]
            await self._process_update(upd)

    async def _process_update(self, upd: dict) -> None:
        msg = upd.get("message", {})
        text = (msg.get("text") or "").strip()
        if not text.startswith(BUS_PREFIX):
            return

        # Only from the right topic
        thread_id = msg.get("message_thread_id", 0)
        if self.topic_id and thread_id != self.topic_id:
            return

        # Skip old messages
        ts = msg.get("date", 0)
        if time.time() - ts > MSG_TTL:
            return

        m = _BUS_RE.match(text)
        if not m:
            return

        frm, to, action, json_str = m.groups()
        if to != self.name:
            return  # not for us

        try:
            payload = json.loads(json_str or "{}")
        except json.JSONDecodeError:
            payload = {}

        handler = self._handlers.get(action)
        if not handler:
            log.debug("[%s] No handler for action '%s'", self.name, action)
            return

        async def reply(response_data: dict):
            await self._reply(frm, action, response_data)

        log.info("[%s] ← %s %s %s", self.name, frm, action, payload)
        try:
            await handler(payload, reply)
        except Exception as e:
            log.error("[%s] Handler '%s' error: %s", self.name, action, e)

    def stop(self):
        self._running = False


# ── Autonomous Scheduler Actions ──────────────────────────────────────────────

class VoodooAutonomousLoop:
    """
    Coordinates autonomous inter-bot communication.
    Runs as a background task within any bot.

    Responsibilities:
    - ContentScheduler asks TeacherBot for word suggestions
    - AnalystBot periodically reports stats to OpsBot
    - GrowthBot sends invite link requests to PublisherBot
    - OpsBot collects health pings from all bots
    """

    def __init__(self, bus: BusClient):
        self.bus = bus

    async def broadcast_health(self) -> None:
        """Ping all bots to report health status."""
        for bot in ["teacher", "scheduler", "analyst", "growth", "publisher", "speak"]:
            await self.bus.send(bot, "ping", {})
        log.info("[auto] Health broadcast sent")

    async def request_daily_word(self, level: str = "B2") -> None:
        """Ask TeacherBot for the word of the day."""
        await self.bus.send("teacher", "get_word", {"level": level})

    async def request_stats_report(self) -> None:
        """Ask AnalystBot for latest stats."""
        await self.bus.send("analyst", "get_stats", {})

    async def notify_new_content(self, content_type: str, text: str) -> None:
        """Inform bots that new content was published."""
        await self.bus.send("speak", "new_content", {"type": content_type, "text": text})
        await self.bus.send("growth", "new_content", {"type": content_type, "text": text})
