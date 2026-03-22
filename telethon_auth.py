"""
telethon_auth.py — One-time Telethon authentication

Run: python3 telethon_auth.py
Enter phone → get code in Telegram → enter code here
Session saved as voodoo_manager.session
"""
import asyncio
import os
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

API_ID   = int(os.getenv("TELETHON_API_ID", "0"))
API_HASH = os.getenv("TELETHON_API_HASH", "")

if not API_ID or not API_HASH:
    print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Спочатку встанови в .env файлі:

TELETHON_API_ID=<число>
TELETHON_API_HASH=<рядок>

Отримай на: https://my.telegram.org/apps
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    exit(1)

async def main():
    client = TelegramClient("voodoo_manager", API_ID, API_HASH)
    await client.start()
    me = await client.get_me()
    print(f"\n✅ Авторизовано як: {me.first_name} (@{me.username})")
    print(f"ID: {me.id}")
    print(f"Сесія збережена: voodoo_manager.session")
    
    # Test: get dialogs
    print("\n📋 Групи:")
    async for d in client.iter_dialogs(limit=10):
        print(f"  {d.name} (id={d.id})")
    
    await client.disconnect()

asyncio.run(main())
