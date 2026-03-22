"""
agents/outreach_agent.py — Voodoo Autonomous Outreach Agent

Self-learning outreach bot that finds Telegram groups, joins them,
posts value-first content, and learns from every action to avoid bans.

Features:
  - Soft / aggressive mode per-market, switchable live via OpsBot
  - 48h cooldown per group (configurable)
  - Ban detection → auto-blacklist + delay increase
  - Learning: tracks best hours, best templates, ban rates
  - Auto-pause if ban rate too high
  - Reports all decisions to OpsBot

Usage:
    python agents/outreach_agent.py --run              # one cycle
    python agents/outreach_agent.py --run --market ru  # one market
    python agents/outreach_agent.py --daemon           # every 6h
    python agents/outreach_agent.py --stats            # stats
    python agents/outreach_agent.py --learn            # show learned patterns
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

# ── Paths ─────────────────────────────────────────────────────────────────────

BASE_DIR      = Path(__file__).parent.parent
CONFIGS_PATH  = BASE_DIR / "data" / "language_configs.json"
STATE_PATH    = BASE_DIR / "data" / "outreach_state.json"
RUNTIME_PATH  = BASE_DIR / "data" / "outreach_runtime.json"
LEARNING_PATH = BASE_DIR / "data" / "outreach_learning.json"

# ── Env ───────────────────────────────────────────────────────────────────────

API_ID    = int(os.getenv("TELETHON_API_ID", "0"))
API_HASH  = os.getenv("TELETHON_API_HASH", "")
SESSION   = os.getenv("TELETHON_SESSION", "voodoo_manager")
ADMIN_ID  = int(os.getenv("ADMIN_CHAT_ID", "0"))
OPS_TOKEN = os.getenv("VOODOO_OPS_BOT_TOKEN", "")

DAEMON_INTERVAL_HOURS = 6


# ══════════════════════════════════════════════════════════════════════════════
# State & config management
# ══════════════════════════════════════════════════════════════════════════════

def _load(path: Path, default: dict) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return default


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def load_state() -> dict:
    return _load(STATE_PATH, {
        "sent": {},
        "joined": [],
        "stats": {"total_sent": 0, "total_joined": 0},
    })


def load_runtime() -> dict:
    return _load(RUNTIME_PATH, {
        "mode": "soft",
        "paused_until": None,
        "cooldown_hours": 48,
        "delay_min": 15,
        "delay_max": 45,
        "max_groups_per_run": 8,
        "markets": {},
    })


def load_learning() -> dict:
    return _load(LEARNING_PATH, {
        "banned_groups": [],
        "group_history": {},
        "template_stats": {},
        "hourly_stats": {},
        "adaptations": [],
        "current_delays": {"min": 15, "max": 45},
        "retire_threshold": 3,   # failures before retiring a template
    })


def save_state(s: dict)    -> None: _save(STATE_PATH, s)
def save_runtime(r: dict)  -> None: _save(RUNTIME_PATH, r)
def save_learning(l: dict) -> None: _save(LEARNING_PATH, l)


# ══════════════════════════════════════════════════════════════════════════════
# Self-learning engine
# ══════════════════════════════════════════════════════════════════════════════

class LearningEngine:
    """Records outcomes, detects patterns, adapts behavior."""

    BAN_ERRORS = (
        "ChatWriteForbiddenError",
        "UserBannedInChannelError",
        "ChannelPrivateError",
        "UserNotParticipantError",
    )

    def __init__(self):
        self.data = load_learning()

    # ── Recording ─────────────────────────────────────────────────────────────

    def record_success(self, group_id: str, market: str, template_idx: int) -> None:
        hour = str(datetime.utcnow().hour)
        gh   = self.data["group_history"].setdefault(group_id, {"ok": 0, "fail": 0, "errors": []})
        gh["ok"] += 1
        gh["last_ok"] = datetime.utcnow().isoformat()

        ts = self.data["template_stats"].setdefault(market, {}).setdefault(str(template_idx), {"sent": 0, "ok": 0, "fail": 0})
        ts["sent"] += 1
        ts["ok"]   += 1

        hs = self.data["hourly_stats"].setdefault(hour, {"ok": 0, "fail": 0})
        hs["ok"] += 1

        save_learning(self.data)

    def record_failure(self, group_id: str, market: str, template_idx: int, error_type: str) -> None:
        hour = str(datetime.utcnow().hour)
        gh   = self.data["group_history"].setdefault(group_id, {"ok": 0, "fail": 0, "errors": []})
        gh["fail"] += 1
        gh["errors"] = (gh.get("errors", []) + [error_type])[-10:]
        gh["last_fail"] = datetime.utcnow().isoformat()

        # Permanent blacklist if hard banned
        if error_type in self.BAN_ERRORS:
            if group_id not in self.data["banned_groups"]:
                self.data["banned_groups"].append(group_id)
                log.warning("🚫 Group %s added to blacklist (%s)", group_id, error_type)

        ts = self.data["template_stats"].setdefault(market, {}).setdefault(str(template_idx), {"sent": 0, "ok": 0, "fail": 0})
        ts["sent"] += 1
        ts["fail"]  += 1

        hs = self.data["hourly_stats"].setdefault(hour, {"ok": 0, "fail": 0})
        hs["fail"] += 1

        save_learning(self.data)

    # ── Analysis ──────────────────────────────────────────────────────────────

    def is_blacklisted(self, group_id: str) -> bool:
        return group_id in self.data["banned_groups"]

    def ban_rate_today(self) -> float:
        """Returns fraction of posts today that resulted in bans."""
        total_ok  = sum(v["ok"]   for v in self.data["hourly_stats"].values())
        total_bad = sum(v["fail"] for v in self.data["hourly_stats"].values())
        total = total_ok + total_bad
        return total_bad / total if total > 0 else 0.0

    def best_templates(self, market: str, templates: list[str]) -> list[str]:
        """Return templates sorted by success rate (worst-performing retired)."""
        stats = self.data["template_stats"].get(market, {})
        threshold = self.data.get("retire_threshold", 3)
        good = []
        for i, t in enumerate(templates):
            st = stats.get(str(i), {"ok": 0, "fail": 0})
            # Retire if too many failures
            if st["fail"] >= threshold and st["ok"] < st["fail"]:
                log.info("Template %d retired (ok=%d fail=%d)", i, st["ok"], st["fail"])
                continue
            good.append((i, t, st.get("ok", 0)))
        # Sort by ok count descending
        good.sort(key=lambda x: -x[2])
        return [t for _, t, _ in good] if good else templates

    def best_posting_hours(self) -> list[int]:
        """Returns hours ranked by success rate."""
        ranked = []
        for h, vals in self.data["hourly_stats"].items():
            total = vals["ok"] + vals["fail"]
            rate  = vals["ok"] / total if total > 0 else 0
            ranked.append((int(h), rate, total))
        ranked.sort(key=lambda x: -x[1])
        return [h for h, _, cnt in ranked if cnt >= 2]

    def get_delays(self, runtime: dict) -> tuple[float, float]:
        """Return current safe delays (from learning or runtime config)."""
        learned = self.data.get("current_delays", {})
        d_min = learned.get("min", runtime.get("delay_min", 15))
        d_max = learned.get("max", runtime.get("delay_max", 45))
        return float(d_min), float(d_max)

    # ── Adaptation ────────────────────────────────────────────────────────────

    async def adapt_if_needed(self) -> str | None:
        """
        Analyze current ban rate and adapt.
        Returns an adaptation message if something changed, else None.
        """
        ban_rate = self.ban_rate_today()
        current_delays = self.data.get("current_delays", {"min": 15, "max": 45})

        adaptations = []

        # High ban rate → increase delays + note adaptation
        if ban_rate > 0.30:
            new_min = min(current_delays["min"] * 2, 120)
            new_max = min(current_delays["max"] * 2, 240)
            if new_min != current_delays["min"]:
                self.data["current_delays"] = {"min": new_min, "max": new_max}
                adaptations.append(
                    f"⚠️ Висока частота банів ({ban_rate:.0%}) → збільшено затримки до {new_min:.0f}-{new_max:.0f}с"
                )

        # Very high ban rate → recommend pause
        if ban_rate > 0.50:
            adaptations.append(
                f"🛑 Критична частота банів ({ban_rate:.0%}) — рекомендую /outpause 12"
            )

        # Successful run → slowly recover delays toward normal
        elif ban_rate < 0.05 and current_delays["min"] > 15:
            new_min = max(current_delays["min"] - 5, 15)
            new_max = max(current_delays["max"] - 10, 45)
            self.data["current_delays"] = {"min": new_min, "max": new_max}
            adaptations.append(f"✅ Низька частота банів → затримки знижено до {new_min:.0f}-{new_max:.0f}с")

        if adaptations:
            entry = {
                "ts": datetime.utcnow().isoformat(),
                "ban_rate": ban_rate,
                "adaptations": adaptations,
            }
            self.data["adaptations"] = (self.data.get("adaptations", []) + [entry])[-50:]
            save_learning(self.data)
            return "\n".join(adaptations)

        return None

    def summary_text(self) -> str:
        """Human-readable learning summary for OpsBot."""
        hs   = self.data["hourly_stats"]
        good_hours = self.best_posting_hours()[:3]
        total_ok  = sum(v["ok"]   for v in hs.values())
        total_bad = sum(v["fail"] for v in hs.values())
        blacklist_count = len(self.data["banned_groups"])
        ban_rate = self.ban_rate_today()
        delays   = self.data.get("current_delays", {"min": 15, "max": 45})
        recent   = self.data.get("adaptations", [])[-3:]

        lines = [
            f"🎓 <b>Outreach Learning Report</b>\n",
            f"📊 Posts today: ✅ {total_ok} ok / ❌ {total_bad} fail ({ban_rate:.0%} ban rate)",
            f"⏱ Current delays: {delays['min']:.0f}–{delays['max']:.0f}s",
            f"🕐 Best hours (UTC): {', '.join(str(h) for h in good_hours) or '—'}",
            f"🚫 Blacklisted groups: {blacklist_count}",
        ]
        if recent:
            lines.append("\n📝 <b>Recent adaptations:</b>")
            for r in recent:
                ts = r["ts"][:16].replace("T", " ")
                for a in r["adaptations"]:
                    lines.append(f"  [{ts}] {a}")

        return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# OpsBot reporting
# ══════════════════════════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════════════════════════
# Core outreach logic
# ══════════════════════════════════════════════════════════════════════════════

def is_on_cooldown(state: dict, group_id: str, cooldown_hours: float) -> bool:
    ts = state["sent"].get(group_id)
    return bool(ts and time.time() - ts < cooldown_hours * 3600)


def mark_sent(state: dict, group_id: str) -> None:
    state["sent"][group_id] = time.time()
    state["stats"]["total_sent"] = state["stats"].get("total_sent", 0) + 1


def mark_joined(state: dict, group_id: str) -> None:
    if group_id not in state["joined"]:
        state["joined"].append(group_id)
    state["stats"]["total_joined"] = len(state["joined"])


async def search_and_join(client, keywords: list[str], state: dict, engine: LearningEngine) -> list:
    """Search for groups, join new ones, return list of chats."""
    from telethon.tl.functions.contacts import SearchRequest
    from telethon.tl.functions.channels import JoinChannelRequest
    from telethon.errors import FloodWaitError, UserAlreadyParticipantError

    found = []

    for kw in keywords:
        log.info("Searching: '%s'", kw)
        try:
            result = await client(SearchRequest(q=kw, limit=8))
            for chat in result.chats:
                # Only supergroups
                if not getattr(chat, "megagroup", False):
                    continue
                gid = str(chat.id)

                # Skip blacklisted
                if engine.is_blacklisted(gid):
                    continue

                if gid not in state["joined"]:
                    try:
                        await client(JoinChannelRequest(chat))
                        mark_joined(state, gid)
                        save_state(state)
                        log.info("Joined: %s", getattr(chat, "title", gid))
                        await asyncio.sleep(random.uniform(12, 25))
                    except UserAlreadyParticipantError:
                        mark_joined(state, gid)
                    except FloodWaitError as e:
                        log.warning("FloodWait: %ds", e.seconds)
                        await asyncio.sleep(e.seconds + 5)
                    except Exception as e:
                        log.debug("Join error %s: %s", gid, e)

                found.append(chat)

        except FloodWaitError as e:
            log.warning("Search FloodWait: %ds", e.seconds)
            await asyncio.sleep(e.seconds + 5)
        except Exception as e:
            log.warning("Search error '%s': %s", kw, e)

        await asyncio.sleep(random.uniform(4, 10))

    return found


async def post_to_groups(
    client,
    groups: list,
    templates: list[str],
    market: str,
    state: dict,
    runtime: dict,
    engine: LearningEngine,
) -> dict:
    """Post to groups respecting cooldowns, blacklist, and learned delays."""
    from telethon.errors import (
        FloodWaitError,
        ChatWriteForbiddenError,
        UserBannedInChannelError,
        ChannelPrivateError,
    )

    sent_count  = 0
    skip_count  = 0
    error_count = 0
    posted      = []

    cooldown  = runtime.get("cooldown_hours", 48)
    max_posts = runtime.get("max_groups_per_run", 8)
    d_min, d_max = engine.get_delays(runtime)

    # Use learning to pick best templates
    good_templates = engine.best_templates(market, templates)
    if not good_templates:
        good_templates = templates  # fallback

    random.shuffle(groups)

    for chat in groups:
        if sent_count >= max_posts:
            break

        gid = str(chat.id)

        if engine.is_blacklisted(gid):
            continue

        if is_on_cooldown(state, gid, cooldown):
            skip_count += 1
            continue

        # Pick template by weight (learning-driven)
        tmpl_idx = random.randint(0, len(good_templates) - 1)
        message  = good_templates[tmpl_idx]
        # Find original index for recording
        orig_idx = templates.index(message) if message in templates else tmpl_idx

        try:
            await client.send_message(chat, message)
            mark_sent(state, gid)
            save_state(state)
            engine.record_success(gid, market, orig_idx)
            sent_count += 1
            posted.append(getattr(chat, "title", gid))
            log.info("✅ Posted to: %s", getattr(chat, "title", gid))

            # Human-like delay with slight randomization
            delay = random.uniform(d_min, d_max)
            # Add extra jitter every 3rd post
            if sent_count % 3 == 0:
                delay += random.uniform(10, 30)
            await asyncio.sleep(delay)

        except FloodWaitError as e:
            log.warning("FloodWait after post: %ds", e.seconds)
            engine.record_failure(gid, market, orig_idx, "FloodWaitError")
            await asyncio.sleep(e.seconds + 10)

        except (ChatWriteForbiddenError, UserBannedInChannelError, ChannelPrivateError) as e:
            err_type = type(e).__name__
            log.warning("🚫 %s in %s → blacklisted", err_type, gid)
            engine.record_failure(gid, market, orig_idx, err_type)
            skip_count += 1

        except Exception as e:
            err_type = type(e).__name__
            log.warning("Post error %s: %s", gid, e)
            engine.record_failure(gid, market, orig_idx, err_type)
            error_count += 1

    return {"sent": sent_count, "skipped": skip_count, "errors": error_count, "groups": posted}


# ══════════════════════════════════════════════════════════════════════════════
# Outreach cycle
# ══════════════════════════════════════════════════════════════════════════════

async def run_outreach_cycle(market_code: str | None = None) -> None:
    """Full cycle: load config → check paused → search → join → post → learn."""
    try:
        from telethon import TelegramClient
    except ImportError:
        log.error("telethon not installed")
        return

    if not API_ID or not API_HASH:
        log.error("TELETHON_API_ID / TELETHON_API_HASH not set")
        return

    runtime = load_runtime()
    state   = load_state()
    cfg     = json.loads(CONFIGS_PATH.read_text())
    engine  = LearningEngine()

    # ── Global pause check ────────────────────────────────────────────────────
    if runtime.get("paused_until"):
        try:
            pause_end = datetime.fromisoformat(runtime["paused_until"])
            if datetime.utcnow() < pause_end:
                remaining = int((pause_end - datetime.utcnow()).total_seconds() / 60)
                log.info("Outreach paused for %d more minutes", remaining)
                return
            else:
                runtime["paused_until"] = None
                save_runtime(runtime)
        except Exception:
            runtime["paused_until"] = None
            save_runtime(runtime)

    # ── Determine markets to run ──────────────────────────────────────────────
    markets_to_run = {}
    for code, market in cfg["markets"].items():
        if market["status"] not in ("active", "pending"):
            continue
        if market_code and code != market_code:
            continue
        mrt = runtime.get("markets", {}).get(code, {})
        if not mrt.get("enabled", True):
            log.info("Market %s disabled in runtime config", code)
            continue
        # Per-market pause
        mrt_pause = mrt.get("paused_until")
        if mrt_pause:
            try:
                if datetime.utcnow() < datetime.fromisoformat(mrt_pause):
                    log.info("Market %s paused", code)
                    continue
                else:
                    runtime["markets"][code]["paused_until"] = None
                    save_runtime(runtime)
            except Exception:
                pass
        markets_to_run[code] = market

    if not markets_to_run:
        log.info("No markets to run for code=%s", market_code)
        return

    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.start()
    log.info("Connected — markets: %s", list(markets_to_run.keys()))

    try:
        total_results = {}

        for code, market in markets_to_run.items():
            flag     = market["flag"]
            lang     = market["language"]
            keywords = market.get("target_keywords", [])

            # Determine mode
            mrt_config = runtime.get("markets", {}).get(code, {})
            mode = mrt_config.get("mode") or runtime.get("mode", "soft")

            if mode == "soft":
                templates = market.get("soft_templates", [])
            elif mode == "aggressive":
                templates = market.get("aggressive_templates", []) + market.get("soft_templates", [])
            else:
                templates = market.get("soft_templates", [])

            if not keywords or not templates:
                log.warning("Market %s missing keywords/templates", code)
                continue

            log.info("=== %s %s [%s mode] ===", flag, lang, mode)

            groups  = await search_and_join(client, keywords, state, engine)
            results = await post_to_groups(client, groups, templates, code, state, runtime, engine)
            total_results[code] = {**results, "mode": mode}
            log.info("%s done: %s", code, results)

            await asyncio.sleep(15)

        # ── Post-cycle adaptation ────────────────────────────────────────────
        adaptation_msg = await engine.adapt_if_needed()

        # ── Report ───────────────────────────────────────────────────────────
        ts    = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
        lines = [f"<b>Outreach cycle</b> — {ts} UTC\n"]
        for code, res in total_results.items():
            m = markets_to_run[code]
            lines.append(
                f"{m['flag']} <b>{m['language']}</b> [{res['mode']}]: "
                f"✅{res['sent']} ⏭{res['skipped']} ❌{res['errors']}"
            )
            if res["groups"]:
                lines.append(f"   → {', '.join(res['groups'][:4])}")

        total = sum(r["sent"] for r in total_results.values())
        lines.append(f"\n<b>Відправлено: {total}</b> | Всього: {state['stats'].get('total_sent', 0)}")

        if adaptation_msg:
            lines.append(f"\n{adaptation_msg}")

        await ops_report("\n".join(lines))

    finally:
        await client.disconnect()


# ══════════════════════════════════════════════════════════════════════════════
# Runtime control (called by OpsBot)
# ══════════════════════════════════════════════════════════════════════════════

def set_mode(mode: str, market: str | None = None) -> str:
    """Switch mode (soft/aggressive) globally or per market."""
    if mode not in ("soft", "aggressive"):
        return "❌ Mode must be 'soft' or 'aggressive'"
    rt = load_runtime()
    if market:
        rt.setdefault("markets", {}).setdefault(market, {})["mode"] = mode
        msg = f"✅ Market <b>{market}</b> switched to <b>{mode}</b> mode"
    else:
        rt["mode"] = mode
        msg = f"✅ Global mode switched to <b>{mode}</b>"
    rt["last_updated"] = datetime.utcnow().isoformat()
    save_runtime(rt)
    return msg


def set_pause(hours: float, market: str | None = None) -> str:
    """Pause outreach for N hours globally or per market."""
    rt     = load_runtime()
    until  = (datetime.utcnow() + timedelta(hours=hours)).isoformat()
    if market:
        rt.setdefault("markets", {}).setdefault(market, {})["paused_until"] = until
        msg = f"⏸ Market <b>{market}</b> paused for <b>{hours:.0f}h</b>"
    else:
        rt["paused_until"] = until
        msg = f"⏸ Outreach paused for <b>{hours:.0f}h</b>"
    rt["last_updated"] = datetime.utcnow().isoformat()
    save_runtime(rt)
    return msg


def set_resume(market: str | None = None) -> str:
    rt = load_runtime()
    if market:
        rt.setdefault("markets", {}).setdefault(market, {})["paused_until"] = None
        msg = f"▶️ Market <b>{market}</b> resumed"
    else:
        rt["paused_until"] = None
        msg = "▶️ Outreach resumed"
    rt["last_updated"] = datetime.utcnow().isoformat()
    save_runtime(rt)
    return msg


def set_cooldown(hours: float) -> str:
    rt = load_runtime()
    rt["cooldown_hours"] = hours
    rt["last_updated"]   = datetime.utcnow().isoformat()
    save_runtime(rt)
    return f"✅ Cooldown set to <b>{hours:.0f}h</b>"


def set_delay(d_min: float, d_max: float) -> str:
    rt = load_runtime()
    rt["delay_min"] = d_min
    rt["delay_max"] = d_max
    rt["last_updated"] = datetime.utcnow().isoformat()
    save_runtime(rt)
    # Also update learning so it takes effect immediately
    l = load_learning()
    l["current_delays"] = {"min": d_min, "max": d_max}
    save_learning(l)
    return f"✅ Delays set to <b>{d_min:.0f}–{d_max:.0f}s</b>"


def set_market_enabled(market: str, enabled: bool) -> str:
    rt = load_runtime()
    rt.setdefault("markets", {}).setdefault(market, {})["enabled"] = enabled
    rt["last_updated"] = datetime.utcnow().isoformat()
    save_runtime(rt)
    action = "enabled" if enabled else "disabled"
    return f"✅ Market <b>{market}</b> {action}"


def reset_blacklist(group_id: str | None = None) -> str:
    l = load_learning()
    if group_id:
        if group_id in l["banned_groups"]:
            l["banned_groups"].remove(group_id)
            save_learning(l)
            return f"✅ Group <code>{group_id}</code> removed from blacklist"
        return f"❌ Group <code>{group_id}</code> not in blacklist"
    else:
        count = len(l["banned_groups"])
        l["banned_groups"] = []
        save_learning(l)
        return f"✅ Cleared {count} groups from blacklist"


def get_stats_text() -> str:
    """Full stats text for OpsBot display."""
    state   = load_state()
    runtime = load_runtime()
    engine  = LearningEngine()
    cfg     = json.loads(CONFIGS_PATH.read_text())

    now = time.time()
    on_cd = sum(1 for ts in state["sent"].values()
                if now - ts < runtime.get("cooldown_hours", 48) * 3600)

    pause_info = ""
    if runtime.get("paused_until"):
        try:
            end = datetime.fromisoformat(runtime["paused_until"])
            if datetime.utcnow() < end:
                mins = int((end - datetime.utcnow()).total_seconds() / 60)
                pause_info = f"\n⏸ Пауза: ще {mins} хв"
        except Exception:
            pass

    mode_icon = "🟡" if runtime.get("mode") == "aggressive" else "🟢"

    lines = [
        f"📣 <b>Outreach Stats</b>{pause_info}\n",
        f"{mode_icon} Режим: <b>{runtime.get('mode', 'soft')}</b>",
        f"⏱ Cooldown: {runtime.get('cooldown_hours', 48):.0f}h",
        f"💤 Delays: {runtime.get('delay_min', 15):.0f}–{runtime.get('delay_max', 45):.0f}s",
        f"\n📊 Всього відправлено: {state['stats'].get('total_sent', 0)}",
        f"👥 Груп приєднано: {state['stats'].get('total_joined', 0)}",
        f"🔴 На кулдауні зараз: {on_cd}",
        f"🚫 В чорному списку: {len(engine.data['banned_groups'])}",
        f"\n🌍 <b>Ринки:</b>",
    ]

    for code, market in cfg["markets"].items():
        mrt  = runtime.get("markets", {}).get(code, {})
        enabled = mrt.get("enabled", True)
        mmode   = mrt.get("mode") or runtime.get("mode", "soft")
        status  = market["status"]
        pause   = "⏸" if mrt.get("paused_until") else ("✅" if enabled else "⛔️")
        lines.append(f"  {market['flag']} {code.upper()} [{status}] {pause} mode={mmode}")

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# Stats & CLI
# ══════════════════════════════════════════════════════════════════════════════

async def show_stats() -> None:
    print(get_stats_text().replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", ""))
    engine = LearningEngine()
    print("\n" + engine.summary_text().replace("<b>", "").replace("</b>", ""))


async def daemon_loop(market_code: str | None = None) -> None:
    log.info("Outreach daemon started (every %dh)", DAEMON_INTERVAL_HOURS)
    await ops_report(
        f"🚀 Outreach daemon started\nInterval: {DAEMON_INTERVAL_HOURS}h\n"
        f"Market: {market_code or 'all'}"
    )
    while True:
        try:
            await run_outreach_cycle(market_code)
        except Exception as e:
            log.error("Daemon cycle error: %s", e)
            await ops_report(f"❌ Outreach cycle error: {e}")
        await asyncio.sleep(DAEMON_INTERVAL_HOURS * 3600)


async def _main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Voodoo Outreach Agent")
    parser.add_argument("--run",    action="store_true")
    parser.add_argument("--daemon", action="store_true")
    parser.add_argument("--stats",  action="store_true")
    parser.add_argument("--learn",  action="store_true")
    parser.add_argument("--market", default=None)
    args = parser.parse_args()

    if args.stats:
        await show_stats()
    elif args.learn:
        engine = LearningEngine()
        print(engine.summary_text().replace("<b>", "").replace("</b>", ""))
    elif args.run:
        await run_outreach_cycle(args.market)
    elif args.daemon:
        await daemon_loop(args.market)
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(_main())
