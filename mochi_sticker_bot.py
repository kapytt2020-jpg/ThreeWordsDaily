"""
mochi_sticker_bot.py — Create & Upload Mochi Telegram Sticker Pack

Modes:
  --export          Export 9 static PNG stickers (512×512)
  --export-animated Export 9 animated WebM video stickers (VP9+alpha, 512×512)
  --upload          Upload static PNGs to Telegram
  --upload-animated Upload animated WebMs to Telegram
  --recreate        Delete old pack and recreate (static)
  --recreate-animated Delete old animated pack and recreate

Requirements:
  pip install python-telegram-bot python-dotenv playwright pillow
  playwright install chromium
  brew install ffmpeg   (for animated stickers only)

Environment (.env):
  LEARNING_BOT_TOKEN or TELEGRAM_BOT_TOKEN  — your bot token
  ADMIN_CHAT_ID                              — your Telegram user_id
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("LEARNING_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_ID: int = int(os.getenv("ADMIN_CHAT_ID", "0"))

STICKERS_DIR         = Path(__file__).parent / "mochi_stickers"
STICKERS_ANIM_DIR    = Path(__file__).parent / "mochi_stickers_anim"
STICKERS_FULL_DIR    = Path(__file__).parent / "mochi_stickers_full"
STICKERS_PREMIUM_DIR = Path(__file__).parent / "mochi_stickers_premium"
HTML_PATH            = Path(__file__).parent / "miniapp" / "mochi_sticker.html"
HTML_FULL_PATH       = Path(__file__).parent / "miniapp" / "mochi_full_sticker.html"
HTML_PREMIUM_PATH    = Path(__file__).parent / "miniapp" / "mochi_premium.html"

PACK_TITLE         = "Mochi — ThreeWordsDaily 🐰"
PACK_TITLE_ANIM    = "Mochi Animated — ThreeWordsDaily 🐰"
PACK_TITLE_FULL    = "Mochi Full — ThreeWordsDaily 🐰"
PACK_TITLE_PREMIUM = "Mochi Premium — ThreeWordsDaily 🐰"

# (expression_id, emoji, base_name)
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

# Premium spring-physics Mochi — 11 expressions
STICKER_SET_PREMIUM: list[tuple[str, str, str]] = [
    ("",          "😶", "mochiprem_default"),
    ("happy",     "😊", "mochiprem_happy"),
    ("love",      "💕", "mochiprem_love"),
    ("sleepy",    "😴", "mochiprem_sleepy"),
    ("surprised", "😮", "mochiprem_surprised"),
    ("excited",   "🌟", "mochiprem_excited"),
    ("sad",       "😢", "mochiprem_sad"),
    ("angry",     "😤", "mochiprem_angry"),
    ("wink",      "😉", "mochiprem_wink"),
    ("dance",     "💃", "mochiprem_dance"),
    ("cool",      "😎", "mochiprem_cool"),
]

# Full-body Mochi — 11 expressions
STICKER_SET_FULL: list[tuple[str, str, str]] = [
    ("",          "😶", "mochifull_default"),
    ("happy",     "😊", "mochifull_happy"),
    ("love",      "💕", "mochifull_love"),
    ("sleepy",    "😴", "mochifull_sleepy"),
    ("surprised", "😮", "mochifull_surprised"),
    ("excited",   "🌟", "mochifull_excited"),
    ("sad",       "😢", "mochifull_sad"),
    ("angry",     "😤", "mochifull_angry"),
    ("wink",      "😉", "mochifull_wink"),
    ("dance",     "💃", "mochifull_dance"),
    ("cool",      "😎", "mochifull_cool"),
]

logging.basicConfig(
    format="%(asctime)s [mochi_bot] %(levelname)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("mochi_bot")


# ---------------------------------------------------------------------------
# EXPORT STATIC PNG
# ---------------------------------------------------------------------------

async def export_sticker_pngs() -> None:
    """Screenshot each expression as 512×512 PNG."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        log.error("Playwright not installed.")
        return

    if not HTML_PATH.exists():
        log.error("HTML not found: %s", HTML_PATH)
        return

    STICKERS_DIR.mkdir(exist_ok=True)
    log.info("Exporting static PNGs to: %s", STICKERS_DIR)

    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        page = await browser.new_page(viewport={"width": 512, "height": 512}, device_scale_factor=1)
        await page.goto(f"file://{HTML_PATH.resolve()}")
        await page.wait_for_timeout(800)

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
            await page.wait_for_timeout(400)
            out_path = STICKERS_DIR / f"{base_name}.png"
            export_el = await page.query_selector("#mochi-export")
            if export_el:
                await page.evaluate("""
                    document.getElementById('mochi-export').style.cssText += ';background:transparent!important;';
                """)
                await export_el.screenshot(path=str(out_path), omit_background=True)
                _resize_png(out_path, 512)
                log.info("  ✅ %s.png  (%s)", base_name, emoji)
            else:
                log.warning("  ⚠️  #mochi-export not found for '%s'", expr_id)

        await browser.close()

    log.info("Export done! %d PNGs in %s", len(STICKER_SET), STICKERS_DIR)


def _resize_png(path: Path, size: int) -> None:
    try:
        from PIL import Image
        img = Image.open(path).convert("RGBA")
        if img.size != (size, size):
            img = img.resize((size, size), Image.LANCZOS)
            img.save(path)
    except ImportError:
        pass


# ---------------------------------------------------------------------------
# EXPORT ANIMATED WebM (VP9 + alpha)
# ---------------------------------------------------------------------------

async def export_sticker_webms() -> None:
    """
    For each expression: capture 60 frames at 30fps (= 2 seconds),
    then use ffmpeg to encode as VP9 WebM with alpha channel.
    Telegram requirements: WebM VP9, 512×512, ≤3s, ≤256KB.
    """
    if not shutil.which("ffmpeg"):
        log.error("ffmpeg not found! Install: brew install ffmpeg")
        log.error("Then re-run: python3 mochi_sticker_bot.py --export-animated")
        return

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        log.error("Playwright not installed.")
        return

    if not HTML_PATH.exists():
        log.error("HTML not found: %s", HTML_PATH)
        return

    STICKERS_ANIM_DIR.mkdir(exist_ok=True)
    frames_root = STICKERS_ANIM_DIR / "_frames"
    frames_root.mkdir(exist_ok=True)

    log.info("Exporting animated WebM stickers to: %s", STICKERS_ANIM_DIR)

    FPS = 30
    DURATION_FRAMES = 60  # 2 seconds @ 30fps

    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        page = await browser.new_page(viewport={"width": 512, "height": 512}, device_scale_factor=1)
        await page.goto(f"file://{HTML_PATH.resolve()}")
        await page.wait_for_timeout(1000)

        # Hide UI
        await page.evaluate("""
            document.querySelector('.topbar').style.display='none';
            document.querySelector('.tag-row').style.display='none';
            document.querySelector('.expr-row').style.display='none';
            document.querySelector('.actions').style.display='none';
            document.querySelector('.screen').style.justifyContent='center';
            document.body.style.background='transparent';
            document.body.style.backgroundColor='transparent';
            document.getElementById('mochi-export').style.cssText += ';background:transparent!important;';
        """)

        for expr_id, emoji, base_name in STICKER_SET:
            log.info("  🎬 Capturing frames for %s (%s)...", base_name, emoji)
            await page.evaluate(f'window.setExpression("{expr_id}")')
            await page.wait_for_timeout(600)  # let particles spawn first

            frame_dir = frames_root / base_name
            frame_dir.mkdir(exist_ok=True)

            export_el = await page.query_selector("#mochi-export")
            if not export_el:
                log.warning("  ⚠️  #mochi-export not found")
                continue

            # Capture frames
            for i in range(DURATION_FRAMES):
                frame_path = frame_dir / f"frame_{i:04d}.png"
                await export_el.screenshot(path=str(frame_path), omit_background=True)
                _resize_png(frame_path, 512)
                await page.wait_for_timeout(1000 // FPS)

            # Encode WebM with ffmpeg (VP9 + alpha)
            out_webm = STICKERS_ANIM_DIR / f"{base_name}.webm"
            ffmpeg_cmd = [
                "ffmpeg", "-y",
                "-framerate", str(FPS),
                "-i", str(frame_dir / "frame_%04d.png"),
                "-c:v", "libvpx-vp9",
                "-pix_fmt", "yuva420p",
                "-b:v", "0",
                "-crf", "18",
                "-auto-alt-ref", "0",
                "-t", "2",
                str(out_webm),
            ]
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
            if result.returncode == 0:
                size_kb = out_webm.stat().st_size / 1024
                log.info("  ✅ %s.webm  (%s)  %.1f KB", base_name, emoji, size_kb)
                if size_kb > 256:
                    log.warning("  ⚠️  File is %.1f KB > 256KB limit, re-encoding smaller...", size_kb)
                    _recompress_webm(out_webm, ffmpeg_cmd)
            else:
                log.error("  ❌ ffmpeg error for %s: %s", base_name, result.stderr[-200:])

        await browser.close()

    # Cleanup frames
    shutil.rmtree(frames_root, ignore_errors=True)
    log.info("Animated export done! WebMs in %s", STICKERS_ANIM_DIR)
    log.info("Next: python3 mochi_sticker_bot.py --upload-animated")


def _recompress_webm(path: Path, original_cmd: list) -> None:
    """Re-encode at higher CRF to reduce file size."""
    cmd = original_cmd.copy()
    for i, arg in enumerate(cmd):
        if arg == "18":
            cmd[i] = "32"
    subprocess.run(cmd, capture_output=True)


# ---------------------------------------------------------------------------
# UPLOAD STATIC PNG PACK
# ---------------------------------------------------------------------------

async def upload_sticker_pack() -> None:
    try:
        from telegram import Bot, InputSticker
        from telegram.constants import StickerFormat
        from telegram.error import TelegramError
    except ImportError:
        log.error("python-telegram-bot not installed.")
        return

    if not BOT_TOKEN or not ADMIN_ID:
        log.error("BOT_TOKEN or ADMIN_CHAT_ID not set in .env")
        return

    bot = Bot(token=BOT_TOKEN)
    me = await bot.get_me()
    pack_name = f"mochi_threewords_by_{me.username}"

    log.info("Bot: @%s | Pack: %s", me.username, pack_name)

    stickers = []
    for _, emoji, base_name in STICKER_SET:
        path = STICKERS_DIR / f"{base_name}.png"
        if not path.exists():
            log.warning("  Missing: %s.png", base_name)
            continue
        with open(path, "rb") as f:
            stickers.append(InputSticker(sticker=f.read(), emoji_list=[emoji], format=StickerFormat.STATIC))
        log.info("  ✅ %s.png  (%s)", base_name, emoji)

    if not stickers:
        log.error("No sticker files. Run --export first.")
        return

    try:
        await bot.create_new_sticker_set(user_id=ADMIN_ID, name=pack_name, title=PACK_TITLE, stickers=stickers)
        url = f"https://t.me/addstickers/{pack_name}"
        log.info("✅ Pack created: %s", url)
        print(f"\n🎉 Pack ready: {url}\n   Share this link with your users!")
    except TelegramError as exc:
        err = str(exc)
        url = f"https://t.me/addstickers/{pack_name}"
        if "already" in err.lower() or "STICKERSET_INVALID" in err:
            log.info("Pack already exists: %s", url)
            print(f"\n📦 Already exists: {url}")
        else:
            log.error("Telegram error: %s", exc)


# ---------------------------------------------------------------------------
# UPLOAD ANIMATED WebM PACK
# ---------------------------------------------------------------------------

async def upload_animated_pack() -> None:
    try:
        from telegram import Bot, InputSticker
        from telegram.constants import StickerFormat
        from telegram.error import TelegramError
    except ImportError:
        log.error("python-telegram-bot not installed.")
        return

    if not BOT_TOKEN or not ADMIN_ID:
        log.error("BOT_TOKEN or ADMIN_CHAT_ID not set in .env")
        return

    if not STICKERS_ANIM_DIR.exists():
        log.error("No animated stickers found. Run --export-animated first.")
        return

    bot = Bot(token=BOT_TOKEN)
    me = await bot.get_me()
    pack_name = f"mochi_anim_by_{me.username}"

    log.info("Bot: @%s | Animated pack: %s", me.username, pack_name)

    stickers = []
    for _, emoji, base_name in STICKER_SET:
        path = STICKERS_ANIM_DIR / f"{base_name}.webm"
        if not path.exists():
            log.warning("  Missing: %s.webm", base_name)
            continue
        with open(path, "rb") as f:
            stickers.append(InputSticker(sticker=f.read(), emoji_list=[emoji], format=StickerFormat.VIDEO))
        size_kb = path.stat().st_size / 1024
        log.info("  ✅ %s.webm  (%s)  %.1f KB", base_name, emoji, size_kb)

    if not stickers:
        log.error("No WebM files found. Run --export-animated first.")
        return

    try:
        await bot.create_new_sticker_set(user_id=ADMIN_ID, name=pack_name, title=PACK_TITLE_ANIM, stickers=stickers)
        url = f"https://t.me/addstickers/{pack_name}"
        log.info("✅ Animated pack created: %s", url)
        print(f"\n🎉 Animated pack ready: {url}\n   Share this link with your users!")
    except TelegramError as exc:
        err = str(exc)
        url = f"https://t.me/addstickers/{pack_name}"
        if "already" in err.lower() or "STICKERSET_INVALID" in err:
            log.info("Pack already exists: %s", url)
            print(f"\n📦 Already exists: {url}")
        else:
            log.error("Telegram error: %s", exc)


# ---------------------------------------------------------------------------
# EXPORT FULL-BODY MOCHI WebM
# ---------------------------------------------------------------------------

async def export_full_webms() -> None:
    if not shutil.which("ffmpeg"):
        log.error("ffmpeg not found! brew install ffmpeg")
        return
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        log.error("Playwright not installed.")
        return
    if not HTML_FULL_PATH.exists():
        log.error("HTML not found: %s", HTML_FULL_PATH)
        return

    STICKERS_FULL_DIR.mkdir(exist_ok=True)
    frames_root = STICKERS_FULL_DIR / "_frames"
    frames_root.mkdir(exist_ok=True)
    log.info("Exporting full-body Mochi WebMs to: %s", STICKERS_FULL_DIR)

    FPS = 30
    DURATION_FRAMES = 60

    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        page = await browser.new_page(viewport={"width": 512, "height": 512}, device_scale_factor=1)
        await page.goto(f"file://{HTML_FULL_PATH.resolve()}")
        await page.wait_for_timeout(1000)

        await page.evaluate("""
            document.querySelectorAll('.topbar,.expr-row,.actions').forEach(function(el){el.style.display='none';});
            document.body.style.background='transparent';
            document.body.style.backgroundColor='transparent';
            document.getElementById('mochi-export').style.cssText += ';background:transparent!important;';
        """)

        for expr_id, emoji, base_name in STICKER_SET_FULL:
            log.info("  🎬 Capturing %s (%s)...", base_name, emoji)
            await page.evaluate(f'window.setExpression("{expr_id}")')
            await page.wait_for_timeout(600)

            frame_dir = frames_root / base_name
            frame_dir.mkdir(exist_ok=True)
            export_el = await page.query_selector("#mochi-export")
            if not export_el:
                log.warning("  ⚠️  #mochi-export not found")
                continue

            for i in range(DURATION_FRAMES):
                frame_path = frame_dir / f"frame_{i:04d}.png"
                await export_el.screenshot(path=str(frame_path), omit_background=True)
                _resize_png(frame_path, 512)
                await page.wait_for_timeout(1000 // FPS)

            out_webm = STICKERS_FULL_DIR / f"{base_name}.webm"
            ffmpeg_cmd = [
                "ffmpeg", "-y", "-framerate", str(FPS),
                "-i", str(frame_dir / "frame_%04d.png"),
                "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
                "-b:v", "0", "-crf", "18", "-auto-alt-ref", "0", "-t", "2",
                str(out_webm),
            ]
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
            if result.returncode == 0:
                size_kb = out_webm.stat().st_size / 1024
                log.info("  ✅ %s.webm (%s) %.1f KB", base_name, emoji, size_kb)
                if size_kb > 256:
                    log.warning("  ⚠️  %.1f KB > 256KB, re-encoding...", size_kb)
                    _recompress_webm(out_webm, ffmpeg_cmd)
            else:
                log.error("  ❌ ffmpeg error for %s: %s", base_name, result.stderr[-200:])

        await browser.close()

    shutil.rmtree(frames_root, ignore_errors=True)
    log.info("Full-body export done! WebMs in %s", STICKERS_FULL_DIR)


async def upload_full_pack() -> None:
    try:
        from telegram import Bot, InputSticker
        from telegram.constants import StickerFormat
        from telegram.error import TelegramError
    except ImportError:
        log.error("python-telegram-bot not installed.")
        return
    if not BOT_TOKEN or not ADMIN_ID:
        log.error("BOT_TOKEN or ADMIN_CHAT_ID not set in .env")
        return
    if not STICKERS_FULL_DIR.exists():
        log.error("No full stickers found. Run --export-full first.")
        return

    bot = Bot(token=BOT_TOKEN)
    me = await bot.get_me()
    pack_name = f"mochi_full_by_{me.username}"
    log.info("Bot: @%s | Pack: %s", me.username, pack_name)

    stickers = []
    for _, emoji, base_name in STICKER_SET_FULL:
        path = STICKERS_FULL_DIR / f"{base_name}.webm"
        if not path.exists():
            log.warning("  Missing: %s.webm", base_name)
            continue
        with open(path, "rb") as f:
            stickers.append(InputSticker(sticker=f.read(), emoji_list=[emoji], format=StickerFormat.VIDEO))
        size_kb = path.stat().st_size / 1024
        log.info("  ✅ %s.webm (%s) %.1f KB", base_name, emoji, size_kb)

    if not stickers:
        log.error("No WebM files. Run --export-full first.")
        return

    try:
        await bot.create_new_sticker_set(user_id=ADMIN_ID, name=pack_name, title=PACK_TITLE_FULL, stickers=stickers)
        url = f"https://t.me/addstickers/{pack_name}"
        log.info("✅ Full pack created: %s", url)
        print(f"\n🎉 Full body pack ready: {url}")
    except TelegramError as exc:
        err = str(exc)
        url = f"https://t.me/addstickers/{pack_name}"
        if "already" in err.lower():
            log.info("Pack already exists: %s", url)
            print(f"\n📦 Already exists: {url}")
        else:
            log.error("Telegram error: %s", exc)


# ---------------------------------------------------------------------------
# EXPORT PREMIUM MOCHI WebM (spring-physics)
# ---------------------------------------------------------------------------

async def export_premium_webms() -> None:
    """
    Export mochi_premium.html as animated WebM stickers.
    Uses spring physics — each expression runs for 2.5 seconds to capture
    the bounce settle + looping motion.
    """
    if not shutil.which("ffmpeg"):
        log.error("ffmpeg not found! brew install ffmpeg")
        return
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        log.error("Playwright not installed.")
        return
    if not HTML_PREMIUM_PATH.exists():
        log.error("HTML not found: %s", HTML_PREMIUM_PATH)
        return

    STICKERS_PREMIUM_DIR.mkdir(exist_ok=True)
    frames_root = STICKERS_PREMIUM_DIR / "_frames"
    frames_root.mkdir(exist_ok=True)
    log.info("Exporting premium Mochi WebMs to: %s", STICKERS_PREMIUM_DIR)

    FPS = 30
    DURATION_FRAMES = 75   # 2.5 seconds — captures spring settle + loop

    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        page = await browser.new_page(viewport={"width": 512, "height": 512}, device_scale_factor=1)
        await page.goto(f"file://{HTML_PREMIUM_PATH.resolve()}")
        await page.wait_for_timeout(1200)

        # Enable export mode (transparent bg) + hide any UI chrome
        await page.evaluate("""
            document.body.classList.add('export-mode');
            document.body.style.background = 'transparent';
            document.body.style.backgroundColor = 'transparent';
            var s = document.getElementById('stage');
            if(s){ s.style.background='transparent'; s.style.backgroundColor='transparent'; }
            var ex = document.getElementById('mochi-export');
            if(ex){
                ex.style.position = 'absolute';
                ex.style.left = '0'; ex.style.top = '0';
                ex.style.width = '512px'; ex.style.height = '512px';
                ex.style.background = 'transparent';
            }
            // hide expression buttons if any
            document.querySelectorAll('.expr-btn-row,.topbar,.actions').forEach(function(el){el.style.display='none';});
        """)

        for expr_id, emoji, base_name in STICKER_SET_PREMIUM:
            log.info("  🎬 Capturing %s (%s)...", base_name, emoji)
            await page.evaluate(f'window.setExpression("{expr_id}")')
            await page.wait_for_timeout(800)  # spring settle

            frame_dir = frames_root / base_name
            frame_dir.mkdir(exist_ok=True)
            export_el = await page.query_selector("#mochi-export")
            if not export_el:
                log.warning("  ⚠️  #mochi-export not found")
                continue

            for i in range(DURATION_FRAMES):
                frame_path = frame_dir / f"frame_{i:04d}.png"
                await export_el.screenshot(path=str(frame_path), omit_background=True)
                _resize_png(frame_path, 512)
                await page.wait_for_timeout(1000 // FPS)

            out_webm = STICKERS_PREMIUM_DIR / f"{base_name}.webm"
            ffmpeg_cmd = [
                "ffmpeg", "-y", "-framerate", str(FPS),
                "-i", str(frame_dir / "frame_%04d.png"),
                "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
                "-b:v", "0", "-crf", "18", "-auto-alt-ref", "0",
                "-t", "2.5",
                str(out_webm),
            ]
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
            if result.returncode == 0:
                size_kb = out_webm.stat().st_size / 1024
                log.info("  ✅ %s.webm (%s) %.1f KB", base_name, emoji, size_kb)
                if size_kb > 256:
                    log.warning("  ⚠️  %.1f KB > 256KB, re-encoding...", size_kb)
                    _recompress_webm(out_webm, ffmpeg_cmd)
            else:
                log.error("  ❌ ffmpeg error for %s: %s", base_name, result.stderr[-300:])

        await browser.close()

    shutil.rmtree(frames_root, ignore_errors=True)
    log.info("Premium export done! WebMs in %s", STICKERS_PREMIUM_DIR)
    log.info("Next: python3 mochi_sticker_bot.py --upload-premium")


async def upload_premium_pack() -> None:
    try:
        from telegram import Bot, InputSticker
        from telegram.constants import StickerFormat
        from telegram.error import TelegramError
    except ImportError:
        log.error("python-telegram-bot not installed.")
        return
    if not BOT_TOKEN or not ADMIN_ID:
        log.error("BOT_TOKEN or ADMIN_CHAT_ID not set in .env")
        return
    if not STICKERS_PREMIUM_DIR.exists():
        log.error("No premium stickers found. Run --export-premium first.")
        return

    bot = Bot(token=BOT_TOKEN)
    me = await bot.get_me()
    pack_name = f"mochi_premium_by_{me.username}"
    log.info("Bot: @%s | Pack: %s", me.username, pack_name)

    stickers = []
    for _, emoji, base_name in STICKER_SET_PREMIUM:
        path = STICKERS_PREMIUM_DIR / f"{base_name}.webm"
        if not path.exists():
            log.warning("  Missing: %s.webm", base_name)
            continue
        with open(path, "rb") as f:
            stickers.append(InputSticker(sticker=f.read(), emoji_list=[emoji], format=StickerFormat.VIDEO))
        size_kb = path.stat().st_size / 1024
        log.info("  ✅ %s.webm (%s) %.1f KB", base_name, emoji, size_kb)

    if not stickers:
        log.error("No WebM files. Run --export-premium first.")
        return

    try:
        await bot.create_new_sticker_set(user_id=ADMIN_ID, name=pack_name, title=PACK_TITLE_PREMIUM, stickers=stickers)
        url = f"https://t.me/addstickers/{pack_name}"
        log.info("✅ Premium pack created: %s", url)
        print(f"\n🎉 Premium Mochi pack ready: {url}\n   Share with your users!")
    except TelegramError as exc:
        err = str(exc)
        url = f"https://t.me/addstickers/{pack_name}"
        if "already" in err.lower():
            log.info("Pack already exists: %s", url)
            print(f"\n📦 Already exists: {url}")
        else:
            log.error("Telegram error: %s", exc)


# ---------------------------------------------------------------------------
# DELETE + RECREATE
# ---------------------------------------------------------------------------

async def delete_and_recreate(animated: bool = False) -> None:
    try:
        from telegram import Bot
    except ImportError:
        return
    bot = Bot(token=BOT_TOKEN)
    me = await bot.get_me()
    pack_name = f"mochi_anim_by_{me.username}" if animated else f"mochi_threewords_by_{me.username}"
    try:
        await bot.delete_sticker_set(name=pack_name)
        log.info("Deleted: %s", pack_name)
    except Exception as exc:
        log.warning("Could not delete (may not exist): %s", exc)
    if animated:
        await upload_animated_pack()
    else:
        await upload_sticker_pack()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    args = sys.argv[1:]

    if "--export-animated" in args:
        print("🎬 Exporting animated Mochi WebM stickers...\n")
        await export_sticker_webms()

    elif "--upload-animated" in args:
        print("📤 Uploading animated Mochi stickers to Telegram...\n")
        await upload_animated_pack()

    elif "--recreate-animated" in args:
        print("♻️  Recreating animated pack...\n")
        await delete_and_recreate(animated=True)

    elif "--export" in args:
        print("📸 Exporting Mochi static PNG stickers...\n")
        await export_sticker_pngs()

    elif "--upload" in args:
        print("📤 Uploading Mochi static stickers to Telegram...\n")
        await upload_sticker_pack()

    elif "--recreate" in args:
        print("♻️  Recreating static pack...\n")
        await delete_and_recreate(animated=False)

    elif "--export-full" in args:
        print("🎬 Exporting full-body Mochi WebM stickers...\n")
        await export_full_webms()

    elif "--upload-full" in args:
        print("📤 Uploading full-body Mochi pack to Telegram...\n")
        await upload_full_pack()

    elif "--export-premium" in args:
        print("🎬 Exporting premium spring-physics Mochi WebM stickers...\n")
        await export_premium_webms()

    elif "--upload-premium" in args:
        print("📤 Uploading premium Mochi pack to Telegram...\n")
        await upload_premium_pack()

    elif "--recreate-premium" in args:
        print("♻️  Recreating premium Mochi pack...\n")
        from telegram import Bot
        bot = Bot(token=BOT_TOKEN)
        me = await bot.get_me()
        try:
            await bot.delete_sticker_set(name=f"mochi_premium_by_{me.username}")
            log.info("Deleted old premium pack")
        except Exception:
            pass
        await upload_premium_pack()

    elif "--recreate-full" in args:
        print("♻️  Recreating full-body Mochi pack...\n")
        from telegram import Bot
        bot = Bot(token=BOT_TOKEN)
        me = await bot.get_me()
        try:
            await bot.delete_sticker_set(name=f"mochi_full_by_{me.username}")
        except Exception:
            pass
        await upload_full_pack()

    else:
        print(__doc__)
        print("=" * 50)
        print(f"Bot token:      {'✅ set' if BOT_TOKEN else '❌ NOT SET'}")
        print(f"Admin ID:       {ADMIN_ID if ADMIN_ID else '❌ NOT SET'}")
        print(f"ffmpeg:         {'✅ found' if shutil.which('ffmpeg') else '❌ not found (brew install ffmpeg)'}")
        print(f"Static PNGs:    {'✅ ' + str(len(list(STICKERS_DIR.glob('*.png')))) + ' files' if STICKERS_DIR.exists() else '❌ run --export'}")
        print(f"Animated WebMs: {'✅ ' + str(len(list(STICKERS_ANIM_DIR.glob('*.webm')))) + ' files' if STICKERS_ANIM_DIR.exists() else '❌ run --export-animated'}")
        print()
        print("Quick start (animated):")
        print("  brew install ffmpeg")
        print("  python3 mochi_sticker_bot.py --export-animated")
        print("  python3 mochi_sticker_bot.py --upload-animated")


if __name__ == "__main__":
    asyncio.run(main())
