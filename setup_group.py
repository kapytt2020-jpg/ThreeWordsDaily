"""
setup_group.py — Auto-detect group ID when bot is added.

Usage: python3 setup_group.py
Then add @VoodooOpsBot to your group as admin.
Script will catch the event, save group ID to .env, and start group_manager.
"""

import asyncio, json, os, re, subprocess, sys
from pathlib import Path
import aiohttp
from dotenv import load_dotenv

load_dotenv()

TOKEN    = os.getenv("VOODOO_OPS_BOT_TOKEN", "")
ENV_FILE = Path(__file__).parent / ".env"
API      = f"https://api.telegram.org/bot{TOKEN}"


def update_env(key: str, value: str) -> None:
    text = ENV_FILE.read_text()
    if re.search(rf"^{key}=", text, re.MULTILINE):
        text = re.sub(rf"^{key}=.*$", f"{key}={value}", text, flags=re.MULTILINE)
    else:
        text += f"\n{key}={value}\n"
    ENV_FILE.write_text(text)
    print(f"✅ Saved {key}={value} to .env")


async def listen_for_group():
    print("\n👂 Чекаю поки @VoodooOpsBot додадуть в групу...")
    print("   → Відкрий Telegram → Групу 'My team' → Додати учасника → @VoodooOpsBot → Зробити адміном\n")

    offset = 0
    async with aiohttp.ClientSession() as session:
        while True:
            async with session.get(
                f"{API}/getUpdates",
                params={"offset": offset, "timeout": 30, "allowed_updates": '["my_chat_member","message"]'}
            ) as r:
                data = await r.json()

            for update in data.get("result", []):
                offset = update["update_id"] + 1

                # Bot added to group
                mcm = update.get("my_chat_member", {})
                chat = mcm.get("chat", {})
                new_member = mcm.get("new_chat_member", {})

                if chat.get("type") in ("group", "supergroup") and new_member.get("status") in ("administrator", "member"):
                    group_id    = chat["id"]
                    group_title = chat.get("title", "?")
                    print(f"\n🎉 Бот доданий в групу: {group_title} (id={group_id})")
                    update_env("INTERNAL_GROUP_ID", str(group_id))
                    print("\n🚀 Запускаю group_manager.py...")
                    os.execv(sys.executable, [sys.executable, "group_manager.py"])
                    return

                # Also catch from regular message if bot was already there
                msg = update.get("message", {})
                msg_chat = msg.get("chat", {})
                if msg_chat.get("type") in ("group", "supergroup"):
                    group_id    = msg_chat["id"]
                    group_title = msg_chat.get("title", "?")
                    current = os.getenv("INTERNAL_GROUP_ID", "0")
                    if current == "0":
                        print(f"\n📨 Повідомлення з групи: {group_title} (id={group_id})")
                        update_env("INTERNAL_GROUP_ID", str(group_id))
                        print("\n🚀 Запускаю group_manager.py...")
                        os.execv(sys.executable, [sys.executable, "group_manager.py"])
                        return


if __name__ == "__main__":
    asyncio.run(listen_for_group())
