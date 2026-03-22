"""
agents/outreach_agent.py — Voodoo Autonomous Outreach Agent

Uses Telethon userbot to:
  1. Search Telegram for target groups by keyword (per language market)
  2. Join them
  3. Post value-first content on a schedule with anti-spam cooldowns
  4. Track sent history in data/outreach_state.json
  5. Report results via OpsBot

Usage:
    python agents/outreach_agent.py --run              # one-shot outreach cycle
    python agents/outreach_agent.py --run --market ru  # only Russian market
    python agents/outreach_agent.py --daemon           # loop every 6h
    python agents/outreach_agent.py --stats            # show stats

The agent runs in SOFT mode by default (value-first messaging).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("outreach_agent")
logging.basicConfig(
    format="%(asctime)s [outreach] %(levelname)s %(message)s",
    level=logging.INFO,
)

# ── Config ────────────────────────────────────────────────────────────────────

API_ID      = int(os.getenv("TELETHON_API_ID", "0"))
API_HASH    = os.getenv("TELETHON_API_HASH", "")
SESSION     = os.getenv("TELETHON_SESSION", "voodoo_manager")
ADMIN_ID    = int(os.getenv("ADMIN_CHAT_ID", "0"))
OPS_TOKEN   = os.getenv("VOODOO_OPS_BOT_TOKEN", "")

CONFIGS_PATH = Path(__file__).parent.parent / "data" / "language_configs.json"
STATE_PATH   = Path(__file__).parent.parent / "data" / "outreach_state.json"

DAEMON_INTERVAL_HOURS = 6   # how often the daemon loop runs
MAX_GROUPS_PER_RUN    = 8   # max groups to post to per cycle
SEND_DELAY_MIN        = 15  # seconds min between posts
SEND_DELAY_MAX        = 45  # seconds max between posts
COOLDOWN_HOURS        = 48  # hours before re-posting to same group


# ── State management ──────────────────────────────────────────────────────────

def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except Exception:
            pass
    return {"sent": {}, "joined": [], "stats": {"total_sent": 0, "total_joined": 0}}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def is_on_cooldown(state: dict, group_id: str) -> bool:
    last_ts = state["sent"].get(group_id)
    if not last_ts:
        return False
    elapsed = time.time() - last_ts
    return elapsed < COOLDOWN_HOURS * 3600


def mark_sent(state: dict, group_id: str) -> None:
    state["sent"][group_id] = time.time()
    state["stats"]["total_sent"] = state["stats"].get("total_sent", 0) + 1


def mark_joined(state: dict, group_id: str) -> None:
    if group_id not in state["joined"]:
        state["joined"].append(group_id)
    state["stats"]["total_joined"] = len(state["joined"])


# ── OpsBot reporting ──────────────────────────────────────────────────────────

async def ops_report(text: str) -> None:
    if not OPS_TOKEN or not ADMIN_ID:
        return
    import httpx
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            await c.post(
                f"https://api.telegram.org/bot{OPS_TOKEN}/sendMessage",
                json={"chat_id": ADMIN_ID, "text": f"📣 [OUTREACH]\n\n{text}", "parse_mode": "HTML"},
            )
    except Exception as e:
        log.warning("ops_report failed: %s", e)


# ── Core outreach logic ───────────────────────────────────────────────────────

async def search_and_join_groups(client, keywords: list[str], state: dict, limit_per_keyword: int = 5) -> list:
    """Search for groups by keywords, join new ones, return list of joined chats."""
    from telethon.tl.functions.contacts import SearchRequest
    from telethon.errors import FloodWaitError, UserAlreadyParticipantError

    found_groups = []

    for keyword in keywords:
        log.info("Searching: '%s'", keyword)
        try:
            results = await client(SearchRequest(q=keyword, limit=limit_per_keyword))
            chats = results.chats
            log.info("Found %d chats for '%s'", len(chats), keyword)

            for chat in chats:
                # Only join public groups/supergroups (not channels)
                if not hasattr(chat, "megagroup") or not chat.megagroup:
                    continue
                # Skip if already joined or on cooldown
                chat_id_str = str(chat.id)
                if chat_id_str in state["joined"]:
                    log.debug("Already joined: %s", getattr(chat, "title", ""))
                    found_groups.append(chat)
                    continue

                try:
                    await client.get_dialogs()  # ensure entities are loaded
                    await client(
                        __import__("telethon.tl.functions.channels", fromlist=["JoinChannelRequest"])
                        .JoinChannelRequest(chat)
                    )
                    mark_joined(state, chat_id_str)
                    save_state(state)
                    log.info("Joined: %s (id=%d)", getattr(chat, "title", ""), chat.id)
                    found_groups.append(chat)
                    await asyncio.sleep(random.uniform(10, 20))  # anti-flood
                except UserAlreadyParticipantError:
                    mark_joined(state, chat_id_str)
                    found_groups.append(chat)
                except FloodWaitError as e:
                    log.warning("FloodWait: sleeping %ds", e.seconds)
                    await asyncio.sleep(e.seconds + 5)
                except Exception as e:
                    log.debug("Could not join %s: %s", getattr(chat, "title", ""), e)

        except FloodWaitError as e:
            log.warning("Search FloodWait: sleeping %ds", e.seconds)
            await asyncio.sleep(e.seconds + 5)
        except Exception as e:
            log.warning("Search error for '%s': %s", keyword, e)

        await asyncio.sleep(random.uniform(3, 8))  # between keyword searches

    return found_groups


async def post_to_groups(client, groups: list, templates: list[str], state: dict, max_groups: int) -> dict:
    """Post a message to groups that are not on cooldown."""
    from telethon.errors import FloodWaitError, ChatWriteForbiddenError, UserBannedInChannelError

    sent_count   = 0
    skip_count   = 0
    error_count  = 0
    posted_names = []

    # Shuffle to vary posting order
    random.shuffle(groups)

    for chat in groups:
        if sent_count >= max_groups:
            break

        chat_id_str = str(chat.id)

        if is_on_cooldown(state, chat_id_str):
            log.debug("On cooldown: %s", getattr(chat, "title", ""))
            skip_count += 1
            continue

        message = random.choice(templates)

        try:
            await client.send_message(chat, message)
            mark_sent(state, chat_id_str)
            save_state(state)
            sent_count += 1
            posted_names.append(getattr(chat, "title", str(chat.id)))
            log.info("Posted to: %s", getattr(chat, "title", ""))

            delay = random.uniform(SEND_DELAY_MIN, SEND_DELAY_MAX)
            log.debug("Waiting %.0fs before next post...", delay)
            await asyncio.sleep(delay)

        except FloodWaitError as e:
            log.warning("FloodWait after post: sleeping %ds", e.seconds)
            await asyncio.sleep(e.seconds + 5)
        except (ChatWriteForbiddenError, UserBannedInChannelError):
            log.info("Cannot write to %s — skipping", getattr(chat, "title", ""))
            skip_count += 1
        except Exception as e:
            log.warning("Post error in %s: %s", getattr(chat, "title", ""), e)
            error_count += 1

    return {
        "sent": sent_count,
        "skipped": skip_count,
        "errors": error_count,
        "groups": posted_names,
    }


# ── Outreach cycle ────────────────────────────────────────────────────────────

async def run_outreach_cycle(market_code: str | None = None) -> None:
    """Run a full outreach cycle: search → join → post."""
    try:
        from telethon import TelegramClient
    except ImportError:
        log.error("telethon not installed — pip install telethon")
        return

    if not API_ID or not API_HASH:
        log.error("TELETHON_API_ID / TELETHON_API_HASH not set in .env")
        return

    cfg   = json.loads(CONFIGS_PATH.read_text())
    state = load_state()

    # Determine which markets to process
    markets_to_run = {}
    for code, market in cfg["markets"].items():
        if market["status"] not in ("active", "pending"):
            continue
        if market_code and code != market_code:
            continue
        markets_to_run[code] = market

    if not markets_to_run:
        log.warning("No active/pending markets to outreach for code=%s", market_code)
        return

    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.start()
    log.info("Telethon connected — running outreach for: %s", list(markets_to_run.keys()))

    try:
        total_results = {}

        for code, market in markets_to_run.items():
            flag     = market["flag"]
            lang     = market["language"]
            keywords = market.get("target_keywords", [])
            templates = market.get("soft_templates", []) + market.get("aggressive_templates", [])

            if not keywords or not templates:
                log.warning("Market %s missing keywords or templates", code)
                continue

            log.info("=== %s %s market ===", flag, lang)

            # Search & join
            groups = await search_and_join_groups(client, keywords, state)
            log.info("Total available groups for %s: %d", code, len(groups))

            # Post
            results = await post_to_groups(
                client, groups, market["soft_templates"], state,
                max_groups=cfg["global"]["max_groups_per_run"],
            )
            total_results[code] = results
            log.info("%s results: %s", code, results)

            await asyncio.sleep(10)  # between markets

        # Build report
        report_lines = [f"<b>Outreach cycle complete</b> — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC\n"]
        for code, res in total_results.items():
            m = markets_to_run[code]
            report_lines.append(
                f"{m['flag']} <b>{m['language']}</b>: "
                f"sent={res['sent']} skipped={res['skipped']} errors={res['errors']}"
            )
            if res["groups"]:
                report_lines.append(f"   → {', '.join(res['groups'][:5])}")

        total_sent = sum(r["sent"] for r in total_results.values())
        report_lines.append(f"\n<b>Total posts this cycle: {total_sent}</b>")
        report_lines.append(f"All-time posts: {state['stats'].get('total_sent', 0)}")
        report_lines.append(f"Groups joined: {state['stats'].get('total_joined', 0)}")

        report = "\n".join(report_lines)
        log.info(report)
        await ops_report(report)

    finally:
        await client.disconnect()


# ── Stats ──────────────────────────────────────────────────────────────────────

async def show_stats() -> None:
    state = load_state()
    stats = state["stats"]

    # Count cooldown-active groups
    now = time.time()
    on_cooldown = sum(
        1 for ts in state["sent"].values()
        if now - ts < COOLDOWN_HOURS * 3600
    )

    print(f"\n📣 Outreach Agent Stats")
    print(f"  Total posts (all-time): {stats.get('total_sent', 0)}")
    print(f"  Groups joined: {stats.get('total_joined', 0)}")
    print(f"  Groups on cooldown now: {on_cooldown}")

    # Per-market group count
    cfg = json.loads(CONFIGS_PATH.read_text())
    print(f"\n  Last 10 posted groups:")
    sorted_sent = sorted(state["sent"].items(), key=lambda x: -x[1])
    for gid, ts in sorted_sent[:10]:
        dt = datetime.utcfromtimestamp(ts).strftime("%m-%d %H:%M")
        cd = "🔴" if now - ts < COOLDOWN_HOURS * 3600 else "🟢"
        print(f"    {cd} {gid} — {dt} UTC")
    print()

    await ops_report(
        f"📊 Outreach stats\n"
        f"Posts: {stats.get('total_sent', 0)}\n"
        f"Groups joined: {stats.get('total_joined', 0)}\n"
        f"On cooldown: {on_cooldown}"
    )


# ── Daemon mode ───────────────────────────────────────────────────────────────

async def daemon_loop(market_code: str | None = None) -> None:
    """Run outreach cycles on a schedule indefinitely."""
    log.info("Outreach daemon started (interval=%dh, market=%s)", DAEMON_INTERVAL_HOURS, market_code or "all")
    await ops_report(
        f"🚀 Outreach daemon started\n"
        f"Interval: {DAEMON_INTERVAL_HOURS}h\n"
        f"Market: {market_code or 'all'}"
    )

    while True:
        try:
            await run_outreach_cycle(market_code)
        except Exception as e:
            log.error("Daemon cycle error: %s", e)
            await ops_report(f"❌ Outreach cycle error: {e}")

        next_run = datetime.utcnow() + timedelta(hours=DAEMON_INTERVAL_HOURS)
        log.info("Next outreach cycle at %s UTC", next_run.strftime("%Y-%m-%d %H:%M"))
        await asyncio.sleep(DAEMON_INTERVAL_HOURS * 3600)


# ── CLI ───────────────────────────────────────────────────────────────────────

async def _main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Voodoo Outreach Agent")
    parser.add_argument("--run",    action="store_true", help="Run one outreach cycle")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon (every 6h)")
    parser.add_argument("--stats",  action="store_true", help="Show stats")
    parser.add_argument("--market", default=None,        help="Limit to specific market (e.g. ru)")
    args = parser.parse_args()

    if args.stats:
        await show_stats()
    elif args.run:
        await run_outreach_cycle(args.market)
    elif args.daemon:
        await daemon_loop(args.market)
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(_main())
