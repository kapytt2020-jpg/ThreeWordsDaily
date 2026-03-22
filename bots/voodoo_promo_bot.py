"""
bots/voodoo_promo_bot.py — VoodooPromoBot

Telegram marketing/outreach bot for the Voodoo English Learning Platform.
Operates in two modes: SOFT (value-first) or AGGRESSIVE (direct promotion).
Admin-only. Stores history in data/promo_state.json.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from telegram import Update
from telegram.error import Forbidden, TelegramError
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    filters,
)

load_dotenv()

logging.basicConfig(
    format="%(asctime)s [promo_bot] %(levelname)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("promo_bot")

TOKEN    = os.getenv("VOODOO_PROMO_BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))

if not TOKEN:
    raise RuntimeError("VOODOO_PROMO_BOT_TOKEN not set")

# ── Config ────────────────────────────────────────────────────────────────────

MODE_SOFT       = "soft"
MODE_AGGRESSIVE = "aggressive"

COOLDOWN_HOURS  = 24          # hours before resending to the same group
RATE_LIMIT_PER_HOUR = 20      # max outgoing messages per hour
SEND_DELAY_SEC  = 3           # seconds between sends in a broadcast

STATE_FILE = Path(__file__).parent.parent / "data" / "promo_state.json"
STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

# ── Current runtime state (in-memory) ────────────────────────────────────────

_current_mode: str = MODE_SOFT
_sent_this_hour: list[float] = []   # timestamps of sends in the current hour

# ── Message templates ─────────────────────────────────────────────────────────

SOFT_TEMPLATES = [
    (
        "Всім привіт! Знайшов крутий безкоштовний бот для вивчення англійської через ігри.\n\n"
        "Там є: словниковий квест, вимовні тренування, щоденні уроки, стрік-система як Duolingo.\n\n"
        "Спробуй: @VoodooEnglishBot"
    ),
    (
        "Якщо вчите англійську — зверніть увагу на @VoodooEnglishBot\n\n"
        "Там не нудні вправи, а ігри: swipe-слова, аукціон, детективні місії.\n"
        "Я особисто юзаю щодня"
    ),
    (
        "Безкоштовна альтернатива Duolingo на українській мові\n\n"
        "@VoodooEnglishBot — навчання через Telegram без реєстрації, просто /start\n\n"
        "Є голосові тренування вимови + 12 міні-ігор"
    ),
]

AGGRESSIVE_TEMPLATES = [
    (
        "@VoodooEnglishBot — топовий бот для англійської\n\n"
        "12 ігор\n"
        "Голосові тренування\n"
        "Щоденні уроки\n"
        "Безкоштовно\n\n"
        "Жми /start і спробуй прямо зараз!"
    ),
    (
        "VOODOO ENGLISH — навчання через гру\n\n"
        "Перестань читати нудні підручники.\n"
        "Починай грати і вчити слова одночасно.\n\n"
        "@VoodooEnglishBot — /start"
    ),
    (
        "Хочеш заговорити англійською?\n\n"
        "@VoodooEnglishBot допоможе:\n"
        "Запам'ятай 100+ слів за тиждень\n"
        "Покращ вимову за 5 хв/день\n"
        "Відстежуй прогрес і стрік\n\n"
        "Безкоштовно. Зараз. /start"
    ),
]

# ── State persistence ─────────────────────────────────────────────────────────

def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception as exc:
            log.warning("Failed to load promo_state.json: %s", exc)
    return {}


def _save_state(state: dict) -> None:
    try:
        STATE_FILE.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        log.error("Failed to save promo_state.json: %s", exc)


# ── Rate limiter ──────────────────────────────────────────────────────────────

def _rate_ok() -> bool:
    """Return True if we are under the per-hour rate limit."""
    now = time.monotonic()
    cutoff = now - 3600
    global _sent_this_hour
    _sent_this_hour = [t for t in _sent_this_hour if t > cutoff]
    return len(_sent_this_hour) < RATE_LIMIT_PER_HOUR


def _record_send() -> None:
    _sent_this_hour.append(time.monotonic())


# ── Core send logic ───────────────────────────────────────────────────────────

def _pick_template(group_id: str, mode: str, state: dict) -> tuple[str, int]:
    """Pick next template for this group, rotating via template_index."""
    entry = state.get(group_id, {})
    last_idx = entry.get("template_index", -1)
    templates = SOFT_TEMPLATES if mode == MODE_SOFT else AGGRESSIVE_TEMPLATES
    next_idx = (last_idx + 1) % len(templates)
    return templates[next_idx], next_idx


def _is_on_cooldown(group_id: str, state: dict) -> bool:
    entry = state.get(group_id, {})
    sent_at = entry.get("sent_at")
    if not sent_at:
        return False
    try:
        last = datetime.fromisoformat(sent_at)
        return datetime.utcnow() - last < timedelta(hours=COOLDOWN_HOURS)
    except Exception:
        return False


async def _send_to_group(
    bot,
    group_id: str,
    mode: str,
    state: dict,
    *,
    dry_run: bool = False,
) -> tuple[bool, str]:
    """
    Attempt to send a promo message to group_id.

    Returns (success, reason_string).
    Mutates state in place on success.
    """
    gid_str = str(group_id)
    entry   = state.get(gid_str, {})

    if entry.get("blocked"):
        return False, "blocked (bot was kicked)"

    if _is_on_cooldown(gid_str, state):
        last = entry.get("sent_at", "?")
        return False, f"cooldown active (last sent {last})"

    if not _rate_ok():
        return False, "rate limit reached (20/hour)"

    template, idx = _pick_template(gid_str, mode, state)

    if dry_run:
        return True, template

    try:
        await bot.send_message(
            chat_id=int(group_id),
            text=template,
            parse_mode=None,
        )
    except Forbidden:
        log.warning("Bot kicked from group %s — marking blocked", group_id)
        state[gid_str] = {**entry, "blocked": True, "blocked_at": datetime.utcnow().isoformat()}
        _save_state(state)
        return False, "bot was kicked — group marked blocked"
    except TelegramError as exc:
        log.error("TelegramError sending to %s: %s", group_id, exc)
        return False, f"TelegramError: {exc}"
    except Exception as exc:
        log.error("Unexpected error sending to %s: %s", group_id, exc)
        return False, f"error: {exc}"

    _record_send()
    state[gid_str] = {
        **entry,
        "sent_at":        datetime.utcnow().isoformat(),
        "mode":           mode,
        "template_index": idx,
        "clicks":         entry.get("clicks", 0),
    }
    _save_state(state)
    log.info("Sent promo to %s (mode=%s, tpl=%d)", group_id, mode, idx)
    return True, "ok"


# ── Admin guard ───────────────────────────────────────────────────────────────

def _admin_only(handler):
    """Decorator: silently ignore non-admin users."""
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not update.effective_user or update.effective_user.id != ADMIN_ID:
            return
        return await handler(update, ctx)
    return wrapper


# ── Command handlers ──────────────────────────────────────────────────────────

@_admin_only
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    global _current_mode
    state = _load_state()
    total = len(state)
    sent  = sum(1 for v in state.values() if v.get("sent_at") and not v.get("blocked"))
    blocked = sum(1 for v in state.values() if v.get("blocked"))

    await update.message.reply_text(
        "VoodooPromoBot\n\n"
        f"Режим: {_current_mode.upper()}\n"
        f"Груп в базі: {total}\n"
        f"Відправлено: {sent}\n"
        f"Заблоковано: {blocked}\n\n"
        "Команди:\n"
        "/soft — м'який режим\n"
        "/aggressive — агресивний режим\n"
        "/preview [group_id] — переглянути повідомлення\n"
        "/send [group_id] — надіслати в групу\n"
        "/broadcast [id1,id2,...] — масова розсилка\n"
        "/stats — детальна статистика\n"
        "/templates — всі шаблони\n"
    )


@_admin_only
async def cmd_soft(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    global _current_mode
    _current_mode = MODE_SOFT
    log.info("Mode switched to SOFT by admin")
    await update.message.reply_text("Режим змінено на: SOFT")


@_admin_only
async def cmd_aggressive(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    global _current_mode
    _current_mode = MODE_AGGRESSIVE
    log.info("Mode switched to AGGRESSIVE by admin")
    await update.message.reply_text("Режим змінено на: AGGRESSIVE")


@_admin_only
async def cmd_preview(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    global _current_mode
    if not ctx.args:
        await update.message.reply_text("Використання: /preview [group_id]")
        return

    group_id = ctx.args[0]
    state    = _load_state()
    _, template = await _send_to_group(
        ctx.bot, group_id, _current_mode, state, dry_run=True
    )

    await update.message.reply_text(
        f"--- PREVIEW (mode={_current_mode.upper()}, group={group_id}) ---\n\n{template}"
    )


@_admin_only
async def cmd_send(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    global _current_mode
    if not ctx.args:
        await update.message.reply_text("Використання: /send [group_id]")
        return

    group_id = ctx.args[0]
    state    = _load_state()
    ok, reason = await _send_to_group(ctx.bot, group_id, _current_mode, state)

    if ok:
        await update.message.reply_text(f"Надіслано до {group_id}")
    else:
        await update.message.reply_text(f"Не вдалося надіслати до {group_id}: {reason}")


@_admin_only
async def cmd_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    global _current_mode
    if not ctx.args:
        await update.message.reply_text(
            "Використання: /broadcast [id1,id2,...]\n"
            "Або: /broadcast id1 id2 id3"
        )
        return

    # Accept comma-separated or space-separated list
    raw   = " ".join(ctx.args)
    ids   = [gid.strip() for gid in raw.replace(",", " ").split() if gid.strip()]
    state = _load_state()

    sent_ok  = []
    sent_err = []

    await update.message.reply_text(
        f"Починаю розсилку до {len(ids)} груп (режим: {_current_mode.upper()})..."
    )

    for gid in ids:
        if not _rate_ok():
            sent_err.append(f"{gid}: rate limit")
            log.warning("Rate limit hit during broadcast, stopping")
            break

        ok, reason = await _send_to_group(ctx.bot, gid, _current_mode, state)
        if ok:
            sent_ok.append(gid)
        else:
            sent_err.append(f"{gid}: {reason}")

        await asyncio.sleep(SEND_DELAY_SEC)

    lines = [f"Розсилка завершена.\n\nУспішно ({len(sent_ok)}):"]
    for gid in sent_ok:
        lines.append(f"  + {gid}")
    if sent_err:
        lines.append(f"\nПомилки ({len(sent_err)}):")
        for e in sent_err:
            lines.append(f"  - {e}")

    await update.message.reply_text("\n".join(lines))


@_admin_only
async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    state   = _load_state()
    total   = len(state)
    sent    = [v for v in state.values() if v.get("sent_at") and not v.get("blocked")]
    blocked = sum(1 for v in state.values() if v.get("blocked"))

    # Acceptance rate: ratio of groups that were ever sent to vs. all groups
    acceptance = f"{len(sent) / total * 100:.1f}%" if total else "N/A"

    # Groups broken down by mode
    by_mode: dict[str, int] = {}
    for v in sent:
        m = v.get("mode", "unknown")
        by_mode[m] = by_mode.get(m, 0) + 1

    hour_sent = len(_sent_this_hour)

    lines = [
        "Статистика VoodooPromoBot\n",
        f"Груп в базі: {total}",
        f"Отримали повідомлення: {len(sent)}",
        f"Заблоковано: {blocked}",
        f"Acceptance rate: {acceptance}",
        f"За останню годину надіслано: {hour_sent}/{RATE_LIMIT_PER_HOUR}",
        "",
        "По режимах:",
    ]
    for mode_name, count in by_mode.items():
        lines.append(f"  {mode_name}: {count}")

    await update.message.reply_text("\n".join(lines))


@_admin_only
async def cmd_templates(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    lines = ["=== SOFT MODE TEMPLATES ===\n"]
    for i, t in enumerate(SOFT_TEMPLATES, 1):
        lines.append(f"[{i}]\n{t}\n")

    lines.append("\n=== AGGRESSIVE MODE TEMPLATES ===\n")
    for i, t in enumerate(AGGRESSIVE_TEMPLATES, 1):
        lines.append(f"[{i}]\n{t}\n")

    await update.message.reply_text("\n".join(lines))


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    app = Application.builder().token(TOKEN).build()

    admin_filter = filters.User(user_id=ADMIN_ID)

    app.add_handler(CommandHandler("start",       cmd_start,      filters=admin_filter))
    app.add_handler(CommandHandler("soft",        cmd_soft,       filters=admin_filter))
    app.add_handler(CommandHandler("aggressive",  cmd_aggressive, filters=admin_filter))
    app.add_handler(CommandHandler("preview",     cmd_preview,    filters=admin_filter))
    app.add_handler(CommandHandler("send",        cmd_send,       filters=admin_filter))
    app.add_handler(CommandHandler("broadcast",   cmd_broadcast,  filters=admin_filter))
    app.add_handler(CommandHandler("stats",       cmd_stats,      filters=admin_filter))
    app.add_handler(CommandHandler("templates",   cmd_templates,  filters=admin_filter))

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    log.info("VoodooPromoBot online (admin_id=%d, mode=%s)", ADMIN_ID, _current_mode)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
