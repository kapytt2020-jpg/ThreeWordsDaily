"""
generate_mochi_ai.py — Generate AI Mochi stickers via DALL-E 3

Usage:
  python3 generate_mochi_ai.py --generate    # generate 9 PNGs (~$0.36)
  python3 generate_mochi_ai.py --upload      # upload to Telegram
  python3 generate_mochi_ai.py --all         # generate + upload
"""
from __future__ import annotations
import asyncio, base64, io, os, sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
BOT_TOKEN  = os.getenv("LEARNING_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_ID   = int(os.getenv("ADMIN_CHAT_ID", "0"))
OUT_DIR    = Path(__file__).parent / "mochi_stickers_ai"

# (emoji, file_base, expression description for prompt)
STICKERS = [
    ("😶", "mochi_default",
     "calm neutral expression, sitting with tiny paws on lap, gentle soft smile, peaceful and relaxed"),
    ("😊", "mochi_happy",
     "huge joyful smile showing happy teeth, very rosy pink cheeks, both arms raised up in pure joy and excitement, golden sparkles bursting all around"),
    ("💕", "mochi_love",
     "adorable heart-shaped eyes glowing red and pink, deeply blushing red cheeks, hugging a giant red heart, small pink floating hearts surrounding the character"),
    ("😴", "mochi_sleepy",
     "eyes completely closed into droopy curved lines, mouth open in a big yawn, three ZZZ bubble letters floating upward, slouched sleepy tired pose, cozy feel"),
    ("😮", "mochi_surprised",
     "extremely wide circular shocked eyes, mouth wide open in perfect O shape, ears shooting straight up in alarm, sharp shock burst lines radiating outward"),
    ("🌟", "mochi_excited",
     "leaping high in the air with pure excitement, massive wide grin, both fists pumping upward, colorful confetti and golden stars exploding all around"),
    ("😢", "mochi_sad",
     "large glistening teary eyes with big sparkling tears streaming down cheeks, trembling bottom lip, drooping floppy sad ears, tiny rain cloud hovering above head"),
    ("😤", "mochi_angry",
     "intensely furrowed angry V-shaped brows, bright red flushed face, dramatic steam puffs blasting from both sides of head, arms crossed tightly, red anger vein symbol on forehead"),
    ("😉", "mochi_wink",
     "right eye closed in a big exaggerated wink, left eye sparkling with stars, wide cheeky confident grin, one paw doing a cute finger-gun pose, sparkle flash burst effect"),
]

BASE_PROMPT = (
    "A single cute kawaii chibi bunny sticker character. "
    "Round chubby soft white fluffy body, oversized round shiny eyes with white sparkle highlights, "
    "small cute pink button nose, stubby round bunny ears with soft pink inner color, "
    "tiny cute rounded paws, plush soft fur texture. "
    "Expression and pose: {expr}. "
    "Art style: professional Japanese kawaii Telegram sticker illustration, "
    "clean thick black outline, vibrant cheerful pastel and saturated colors, "
    "pure white background, character centered with slight margin, "
    "high quality clean digital art, no text, no watermark, no extra characters."
)


def _ensure_pkg(pkg: str, import_name: str | None = None) -> None:
    name = import_name or pkg
    try:
        __import__(name)
    except ImportError:
        print(f"  Installing {pkg}...")
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", pkg], check=True)


async def generate_all() -> None:
    _ensure_pkg("openai")
    _ensure_pkg("rembg")
    _ensure_pkg("pillow", "PIL")

    from openai import AsyncOpenAI
    from rembg import remove as rembg_remove
    from PIL import Image

    if not OPENAI_KEY:
        print("ERROR: OPENAI_API_KEY not set in .env")
        return

    client = AsyncOpenAI(api_key=OPENAI_KEY)
    OUT_DIR.mkdir(exist_ok=True)
    total = len(STICKERS)

    print(f"Generating {total} Mochi AI stickers with DALL-E 3...\n")

    for idx, (emoji, name, expr) in enumerate(STICKERS, 1):
        out_path = OUT_DIR / f"{name}.png"
        if out_path.exists():
            print(f"  ⏭️  [{idx}/{total}] {name}.png already exists, skipping")
            continue

        print(f"  🎨 [{idx}/{total}] {name} {emoji} ...")
        prompt = BASE_PROMPT.format(expr=expr)

        try:
            resp = await client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="hd",
                n=1,
                response_format="b64_json",
            )
            raw_bytes = base64.b64decode(resp.data[0].b64_json)

            print(f"         Removing background...")
            no_bg_bytes = rembg_remove(raw_bytes)

            img = Image.open(io.BytesIO(no_bg_bytes)).convert("RGBA")
            img = img.resize((512, 512), Image.LANCZOS)
            img.save(out_path, "PNG")

            kb = out_path.stat().st_size / 1024
            print(f"  ✅ [{idx}/{total}] {name}.png — {kb:.0f} KB\n")

        except Exception as exc:
            print(f"  ❌ [{idx}/{total}] Error generating {name}: {exc}\n")

    done = len(list(OUT_DIR.glob("*.png")))
    print(f"Done! {done}/{total} stickers saved in {OUT_DIR}")
    if done > 0:
        print(f"\nNext: python3 generate_mochi_ai.py --upload")


async def upload_ai_pack() -> None:
    _ensure_pkg("python-telegram-bot", "telegram")

    from telegram import Bot, InputSticker
    from telegram.constants import StickerFormat
    from telegram.error import TelegramError

    if not BOT_TOKEN or not ADMIN_ID:
        print("ERROR: BOT_TOKEN or ADMIN_CHAT_ID not set in .env")
        return

    files = list(OUT_DIR.glob("*.png"))
    if not files:
        print("No AI stickers found. Run --generate first.")
        return

    bot = Bot(token=BOT_TOKEN)
    me = await bot.get_me()
    pack_name  = f"mochi_ai_by_{me.username}"
    pack_title = "Mochi AI — ThreeWordsDaily 🐰✨"

    print(f"Bot: @{me.username} | Pack: {pack_name}\n")

    stickers = []
    for emoji, name, _ in STICKERS:
        path = OUT_DIR / f"{name}.png"
        if not path.exists():
            print(f"  ⚠️  Missing {name}.png")
            continue
        with open(path, "rb") as f:
            stickers.append(InputSticker(sticker=f.read(), emoji_list=[emoji], format=StickerFormat.STATIC))
        print(f"  ✅ {name}.png {emoji}")

    if not stickers:
        print("No sticker files to upload.")
        return

    # Delete old pack if exists
    try:
        await bot.delete_sticker_set(name=pack_name)
        print(f"\nDeleted old pack: {pack_name}")
    except Exception:
        pass

    try:
        await bot.create_new_sticker_set(
            user_id=ADMIN_ID, name=pack_name,
            title=pack_title, stickers=stickers
        )
        url = f"https://t.me/addstickers/{pack_name}"
        print(f"\n🎉 AI Pack ready: {url}")
        print("Share this link with your users!")
    except TelegramError as exc:
        print(f"Telegram error: {exc}")


async def main() -> None:
    args = sys.argv[1:]
    if "--all" in args:
        await generate_all()
        await upload_ai_pack()
    elif "--generate" in args:
        await generate_all()
    elif "--upload" in args:
        await upload_ai_pack()
    else:
        print(__doc__)
        print("=" * 50)
        ai_count = len(list(OUT_DIR.glob("*.png"))) if OUT_DIR.exists() else 0
        print(f"OpenAI key: {'✅ set' if OPENAI_KEY else '❌ NOT SET'}")
        print(f"AI stickers: {ai_count}/9 generated")


if __name__ == "__main__":
    asyncio.run(main())
