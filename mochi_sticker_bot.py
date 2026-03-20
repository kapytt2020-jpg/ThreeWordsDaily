"""
mochi_sticker_bot.py — Create & Upload Mochi Telegram Sticker Pack

Two modes:
  --export    Use Playwright to render mochi_sticker.html and export 9 PNG stickers (512×512)
  --upload    Upload PNGs to Telegram via Bot API, create sticker pack

Requirements:
  pip install python-telegram-bot python-dotenv playwright
  playwright install chromium

Environment (.env):
  LEARNING_BOT_TOKEN or TELEGRAM_BOT_TOKEN  — your bot token
  ADMIN_CHAT_ID                              — your Telegram user_id (must have started the bot)

Usage:
  python3 mochi_sticker_bot.py --export   # exports PNGs to ./mochi_stickers/
  python3 mochi_sticker_bot.py --upload   # creates the sticker pack in Telegram
  python3 mochi_sticker_bot.py            # shows this help

After --upload, the sticker pack link is printed.
Share it in Telegram: https://t.me/addstickers/<pack_name>
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BOT_TOKEN: str = os.getenv("LEARNING_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_ID: int = int(os.getenv("ADMIN_CHAT_ID", "0"))

STICKERS_DIR = Path(__file__).parent / "mochi_stickers"
HTML_PATH = Path(__file__).parent / "miniapp" / "mochi_sticker.html"

PACK_TITLE = "Mochi — ThreeWordsDaily 🐰"

# Each sticker: (expression_id, emoji, file_base_name)
STICKER_SET: list[tuple[str, str, str]] = [
    ("",          "😶", "mochi_default"),
    ("happy",     "😊", "mochi_happy"),
    ("love",      "💕", "mochi_love"),
    ("sleepy",    "😴", "mochi_sleepy"),
    ("surprised", "😮", "mochi_surprised"),
    ("excited",   "🌟", "mochi_excited"),
    ("sad",       "😢", "mochi_sad"),
    ("angry",     "😤", "mochi_angry"),
    ("wink",      "😉", "mochi_wink"),
]

logging.basicConfig(
    format="%(asctime)s [mochi_bot] %(levelname)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("mochi_bot")

# ---------------------------------------------------------------------------
# EXPORT: render PNGs via Playwright
# ---------------------------------------------------------------------------

async def export_sticker_pngs() -> None:
    """Screenshot each Mochi expression from mochi_sticker.html at 512×512."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        log.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
        return

    if not HTML_PATH.exists():
        log.error("HTML not found: %s", HTML_PATH)
        return

    STICKERS_DIR.mkdir(exist_ok=True)
    log.info("Exporting stickers to: %s", STICKERS_DIR)

    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        page = await browser.new_page(
            viewport={"width": 512, "height": 512},
            device_scale_factor=1,
        )
        await page.goto(f"file://{HTML_PATH.resolve()}")
        await page.wait_for_timeout(800)

        # Hide UI elements — export only the stage area
        await page.evaluate("""
            document.querySelector('.topbar').style.display='none';
            document.querySelector('.tag-row').style.display='none';
            document.querySelector('.expr-row').style.display='none';
            document.querySelector('.actions').style.display='none';
            document.querySelector('.screen').style.justifyContent='center';
            document.body.style.background='transparent';
            document.body.style.backgroundColor='transparent';
        """)

        for expr_id, emoji, base_name in STICKER_SET:
            await page.evaluate(f'window.setExpression("{expr_id}")')
            await page.wait_for_timeout(350)

            out_path = STICKERS_DIR / f"{base_name}.png"

            # Screenshot just the mochi-export div
            export_el = await page.query_selector("#mochi-export")
            if export_el:
                # Make background transparent for sticker
                await page.evaluate("""
                    document.getElementById('mochi-export').style.background='transparent';
                    document.getElementById('mochi-export').style.cssText += ';background:transparent!important;';
                """)
                await export_el.screenshot(path=str(out_path), omit_background=True)
                log.info("  ✅ %s.png  (%s)", base_name, emoji)
            else:
                log.warning("  ⚠️  Could not find #mochi-export for expr '%s'", expr_id)

        await browser.close()

    log.info("Export done! %d stickers in %s", len(STICKER_SET), STICKERS_DIR)
    log.info("Next: python3 mochi_sticker_bot.py --upload")


# ---------------------------------------------------------------------------
# UPLOAD: create Telegram sticker pack via Bot API
# ---------------------------------------------------------------------------

async def upload_sticker_pack() -> None:
    """Create Mochi sticker pack in Telegram using python-telegram-bot."""
    try:
        from telegram import Bot, InputSticker
        from telegram.constants import StickerFormat
        from telegram.error import TelegramError
    except ImportError:
        log.error("python-telegram-bot not installed. Run: pip install 'python-telegram-bot>=21'")
        return

    if not BOT_TOKEN:
        log.error("BOT_TOKEN not set in .env (set LEARNING_BOT_TOKEN or TELEGRAM_BOT_TOKEN)")
        return
    if not ADMIN_ID:
        log.error("ADMIN_CHAT_ID not set in .env")
        return
    if not STICKERS_DIR.exists():
        log.error("Stickers dir not found. Run --export first.")
        return

    bot = Bot(token=BOT_TOKEN)
    me = await bot.get_me()
    pack_name = f"mochi_threewords_by_{me.username}"

    log.info("Bot: @%s", me.username)
    log.info("Pack name: %s", pack_name)
    log.info("Pack title: %s", PACK_TITLE)
    log.info("Owner user_id: %d", ADMIN_ID)

    # Build sticker list
    stickers: list[InputSticker] = []
    missing = []
    for expr_id, emoji, base_name in STICKER_SET:
        path = STICKERS_DIR / f"{base_name}.png"
        if not path.exists():
            missing.append(base_name)
            log.warning("  ⚠️  Missing: %s.png", base_name)
            continue
        with open(path, "rb") as f:
            sticker = InputSticker(
                sticker=f.read(),
                emoji_list=[emoji],
                format=StickerFormat.STATIC,
            )
            stickers.append(sticker)
        log.info("  ✅ %s.png  (%s)", base_name, emoji)

    if missing:
        log.warning("Missing %d stickers. Run --export first.", len(missing))

    if not stickers:
        log.error("No sticker files found. Aborting.")
        return

    # Try to create the pack
    try:
        result = await bot.create_new_sticker_set(
            user_id=ADMIN_ID,
            name=pack_name,
            title=PACK_TITLE,
            stickers=stickers,
        )
        if result:
            url = f"https://t.me/addstickers/{pack_name}"
            log.info("\n✅ Sticker pack created!")
            log.info("   Link: %s", url)
            print(f"\n🎉 Pack ready: {url}")
            print(f"   Send this link in Telegram to add Mochi stickers!")

    except TelegramError as exc:
        err = str(exc)
        if "STICKERSET_INVALID" in err or "already" in err.lower() or "name" in err.lower():
            url = f"https://t.me/addstickers/{pack_name}"
            log.info("Pack already exists: %s", url)
            print(f"\n📦 Pack already exists: {url}")
        else:
            log.error("Telegram error: %s", exc)
            # Try adding stickers to existing pack instead
            log.info("Attempting to add stickers to existing pack...")
            try:
                for sticker in stickers[:3]:  # Add first 3 as test
                    await bot.add_sticker_to_set(
                        user_id=ADMIN_ID,
                        name=pack_name,
                        sticker=sticker,
                    )
                log.info("Added stickers to existing pack.")
            except Exception as e2:
                log.error("Could not add to existing pack: %s", e2)


# ---------------------------------------------------------------------------
# ADD TO EXISTING SET (update / refresh)
# ---------------------------------------------------------------------------

async def delete_and_recreate() -> None:
    """Delete the existing pack and recreate from scratch. Use when updating designs."""
    try:
        from telegram import Bot
        from telegram.error import TelegramError
    except ImportError:
        return

    if not BOT_TOKEN or not ADMIN_ID:
        log.error("BOT_TOKEN or ADMIN_CHAT_ID not set")
        return

    bot = Bot(token=BOT_TOKEN)
    me = await bot.get_me()
    pack_name = f"mochi_threewords_by_{me.username}"

    try:
        await bot.delete_sticker_set(name=pack_name)
        log.info("Deleted pack: %s", pack_name)
    except Exception as exc:
        log.warning("Could not delete pack (may not exist): %s", exc)

    await upload_sticker_pack()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    if "--export" in sys.argv:
        print("📸 Exporting Mochi sticker PNGs via Playwright...\n")
        await export_sticker_pngs()

    elif "--upload" in sys.argv:
        print("📤 Uploading Mochi sticker pack to Telegram...\n")
        await upload_sticker_pack()

    elif "--recreate" in sys.argv:
        print("♻️  Deleting old pack and recreating...\n")
        await delete_and_recreate()

    else:
        print(__doc__)
        print("=" * 50)
        print(f"Bot token:    {'✅ set' if BOT_TOKEN else '❌ NOT SET'}")
        print(f"Admin ID:     {ADMIN_ID if ADMIN_ID else '❌ NOT SET'}")
        print(f"HTML source:  {'✅ found' if HTML_PATH.exists() else '❌ not found — run from project root'}")
        print(f"Stickers dir: {'✅ ' + str(len(list(STICKERS_DIR.glob('*.png')))) + ' PNGs' if STICKERS_DIR.exists() else '❌ not found — run --export first'}")
        print()
        print("Quick start:")
        print("  1.  python3 mochi_sticker_bot.py --export")
        print("  2.  python3 mochi_sticker_bot.py --upload")


if __name__ == "__main__":
    asyncio.run(main())
