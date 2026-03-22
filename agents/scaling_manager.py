"""
agents/scaling_manager.py — Voodoo Autonomous Scaling Manager

Creates new Telegram groups/channels for each language market,
sets up forum topics, and registers everything in language_configs.json.

Usage:
    python agents/scaling_manager.py --market ru   # bootstrap Russian market
    python agents/scaling_manager.py --list         # show all markets
    python agents/scaling_manager.py --status       # check active groups

Telethon userbot does the heavy lifting (creating groups needs a real account,
not a bot token).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("scaling_manager")
logging.basicConfig(
    format="%(asctime)s [scaling] %(levelname)s %(message)s",
    level=logging.INFO,
)

# ── Paths ─────────────────────────────────────────────────────────────────────

CONFIGS_PATH = Path(__file__).parent.parent / "data" / "language_configs.json"

# ── Telethon credentials ───────────────────────────────────────────────────────

API_ID      = int(os.getenv("TELETHON_API_ID", "0"))
API_HASH    = os.getenv("TELETHON_API_HASH", "")
SESSION     = os.getenv("TELETHON_SESSION", "voodoo_manager")
ADMIN_ID    = int(os.getenv("ADMIN_CHAT_ID", "0"))
OPS_TOKEN   = os.getenv("VOODOO_OPS_BOT_TOKEN", "")

# Bot usernames to add as admins in new groups
BOT_ADMINS = [
    "VoodooEnglishBot",
    "VoodooTeacherBot",
    "VoodooPublisherBot",
]


# ── Config helpers ─────────────────────────────────────────────────────────────

def load_configs() -> dict:
    return json.loads(CONFIGS_PATH.read_text())


def save_configs(cfg: dict) -> None:
    CONFIGS_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))
    log.info("Saved language_configs.json")


def get_market(cfg: dict, market_code: str) -> dict | None:
    return cfg["markets"].get(market_code)


# ── Ops reporting ─────────────────────────────────────────────────────────────

async def ops_report(text: str) -> None:
    if not OPS_TOKEN or not ADMIN_ID:
        return
    import httpx
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            await c.post(
                f"https://api.telegram.org/bot{OPS_TOKEN}/sendMessage",
                json={"chat_id": ADMIN_ID, "text": f"📈 [SCALING]\n\n{text}", "parse_mode": "HTML"},
            )
    except Exception as e:
        log.warning("ops_report failed: %s", e)


# ── Market bootstrap ───────────────────────────────────────────────────────────

async def bootstrap_market(market_code: str) -> None:
    """Create group + channel + topics for a new language market."""
    try:
        from telethon import TelegramClient
        from telethon.tl.functions.channels import (
            CreateChannelRequest,
            InviteToChannelRequest,
        )
        from telethon.tl.functions.messages import (
            CreateChatRequest,
            MigrateChatRequest,
        )
        from telethon.tl.types import InputUser
    except ImportError:
        log.error("telethon not installed — pip install telethon")
        return

    cfg = load_configs()
    market = get_market(cfg, market_code)
    if not market:
        log.error("Unknown market: %s", market_code)
        return

    if market["status"] == "active":
        log.warning("Market %s is already active (group_id=%d)", market_code, market["group_id"])
        return

    flag = market["flag"]
    lang = market["language"]
    log.info("Bootstrapping %s %s market...", flag, lang)

    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.start()

    try:
        # ── 1. Create supergroup (forum) ───────────────────────────────────────
        group_title = f"Voodoo English — {lang} Community"
        log.info("Creating group: %s", group_title)

        # Create regular group first, then migrate to supergroup
        result = await client(CreateChatRequest(
            users=[],
            title=group_title,
        ))
        basic_chat_id = result.chats[0].id
        log.info("Basic chat created: %d", basic_chat_id)

        # Migrate to supergroup
        migrate_result = await client(MigrateChatRequest(chat_id=basic_chat_id))
        # Get the new supergroup
        new_group = None
        for chat in migrate_result.chats:
            if hasattr(chat, "megagroup") and chat.megagroup:
                new_group = chat
                break

        if not new_group:
            log.error("Migration failed — no supergroup found")
            return

        group_id = int(f"-100{new_group.id}")
        log.info("Supergroup created: %d", group_id)

        # ── 2. Enable forum topics ─────────────────────────────────────────────
        try:
            from telethon.tl.functions.channels import ToggleForumRequest
            await client(ToggleForumRequest(channel=new_group, enabled=True))
            log.info("Forum topics enabled")
        except Exception as e:
            log.warning("Could not enable forum: %s (Telegram may do this automatically)", e)

        # ── 3. Create channel ──────────────────────────────────────────────────
        channel_title = f"Voodoo English {flag} | {lang}"
        channel_desc  = f"Безкоштовні уроки англійської для {lang.lower()}-мовних • @VoodooEnglishBot"

        ch_result = await client(CreateChannelRequest(
            title=channel_title,
            about=channel_desc,
            megagroup=False,
            broadcast=True,
        ))
        channel = ch_result.chats[0]
        channel_id = int(f"-100{channel.id}")
        log.info("Channel created: %d", channel_id)

        # ── 4. Invite bots as admins to the group ─────────────────────────────
        from telethon.tl.functions.channels import EditAdminRequest
        from telethon.tl.types import ChatAdminRights

        admin_rights = ChatAdminRights(
            change_info=True,
            post_messages=True,
            edit_messages=True,
            delete_messages=True,
            ban_users=True,
            invite_users=True,
            pin_messages=True,
            manage_call=False,
        )

        for bot_username in BOT_ADMINS:
            try:
                bot_entity = await client.get_entity(bot_username)
                await client(InviteToChannelRequest(channel=new_group, users=[bot_entity]))
                await client(EditAdminRequest(
                    channel=new_group,
                    user_id=bot_entity,
                    admin_rights=admin_rights,
                    rank=f"Voodoo Bot",
                ))
                log.info("Added %s as admin", bot_username)
                await asyncio.sleep(2)
            except Exception as e:
                log.warning("Could not add %s: %s", bot_username, e)

        # ── 5. Create default forum topics ────────────────────────────────────
        topics = {}
        topic_defs = [
            ("📚 Слово дня", "word_of_day"),
            ("🎓 Уроки", "lessons"),
            ("🎙 Подкаст", "podcast"),
            ("🤖 Bot Bus", "bot_bus"),
        ]

        try:
            from telethon.tl.functions.channels import CreateForumTopicRequest

            for topic_name, topic_key in topic_defs:
                try:
                    topic_result = await client(CreateForumTopicRequest(
                        channel=new_group,
                        title=topic_name,
                        random_id=int(asyncio.get_event_loop().time() * 1000) % 2**31,
                    ))
                    thread_id = topic_result.updates[0].message.id
                    topics[topic_key] = thread_id
                    log.info("Topic '%s' created (thread_id=%d)", topic_name, thread_id)
                    await asyncio.sleep(1)
                except Exception as e:
                    log.warning("Could not create topic '%s': %s", topic_name, e)
        except ImportError:
            log.warning("CreateForumTopicRequest not available in this Telethon version")

        # ── 6. Update language_configs.json ───────────────────────────────────
        cfg["markets"][market_code].update({
            "status": "active",
            "group_id": group_id,
            "channel_id": channel_id,
            "topics": topics,
        })
        save_configs(cfg)

        summary = (
            f"{flag} <b>{lang} market bootstrapped!</b>\n\n"
            f"Group: <code>{group_id}</code>\n"
            f"Channel: <code>{channel_id}</code>\n"
            f"Topics: {list(topics.keys())}\n"
            f"Bots added: {BOT_ADMINS}"
        )
        log.info("Bootstrap complete:\n%s", summary)
        await ops_report(summary)

    except Exception as e:
        log.error("Bootstrap failed for %s: %s", market_code, e)
        await ops_report(f"❌ Bootstrap FAILED for {market_code}: {e}")
    finally:
        await client.disconnect()


# ── Status ────────────────────────────────────────────────────────────────────

async def show_status() -> None:
    """Print status of all markets."""
    cfg = load_configs()
    lines = ["🌍 <b>Voodoo Market Status</b>\n"]
    for code, market in cfg["markets"].items():
        flag   = market["flag"]
        lang   = market["language"]
        status = market["status"]
        gid    = market.get("group_id", 0)
        emoji  = {"active": "✅", "pending": "⏳", "planned": "📋"}.get(status, "❓")
        lines.append(f"{emoji} {flag} <b>{lang}</b> [{code}] — {status}")
        if gid:
            lines.append(f"   Group: <code>{gid}</code>")
        else:
            lines.append(f"   Group: not created")
    print("\n".join(lines))
    await ops_report("\n".join(lines))


def list_markets() -> None:
    cfg = load_configs()
    print(f"\n{'CODE':<6} {'FLAG':<4} {'LANGUAGE':<12} {'STATUS':<10} {'GROUP_ID'}")
    print("-" * 60)
    for code, m in cfg["markets"].items():
        gid = m.get("group_id", 0) or "—"
        print(f"{code:<6} {m['flag']:<4} {m['language']:<12} {m['status']:<10} {gid}")
    print()


# ── Autonomous check-and-expand ───────────────────────────────────────────────

async def auto_expand() -> None:
    """
    Automatically bootstrap any 'pending' markets.
    Called by the autonomous loop when growth thresholds are met.
    """
    cfg = load_configs()
    for code, market in cfg["markets"].items():
        if market["status"] == "pending":
            log.info("Auto-expanding to %s %s market", market["flag"], market["language"])
            await bootstrap_market(code)
            await asyncio.sleep(10)  # space out creations


# ── CLI ───────────────────────────────────────────────────────────────────────

async def _main() -> None:
    parser = argparse.ArgumentParser(description="Voodoo Scaling Manager")
    parser.add_argument("--market",  help="Bootstrap this market code (e.g. ru, pl)")
    parser.add_argument("--list",    action="store_true", help="List all markets")
    parser.add_argument("--status",  action="store_true", help="Show status with ops report")
    parser.add_argument("--expand",  action="store_true", help="Auto-expand all pending markets")
    args = parser.parse_args()

    if args.list:
        list_markets()
    elif args.status:
        await show_status()
    elif args.market:
        await bootstrap_market(args.market)
    elif args.expand:
        await auto_expand()
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(_main())
