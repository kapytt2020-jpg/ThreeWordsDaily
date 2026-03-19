"""
Group Poster — Telethon
Постить в групи як РЕАЛЬНИЙ КОРИСТУВАЧ (не бот)
Бот не може постити в групи де він не адмін — Telethon може

Налаштування:
1. pip install telethon
2. Отримай API_ID і API_HASH на https://my.telegram.org
3. Заповни .env файл
4. Перший запуск — введеш номер телефону і код
"""

import asyncio
import os
import json
import random
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import FloodWaitError, UserBannedInChannelError

load_dotenv()

API_ID = int(os.getenv('TELEGRAM_API_ID', '0'))
API_HASH = os.getenv('TELEGRAM_API_HASH', '')
PHONE = os.getenv('TELEGRAM_PHONE', '')
ADMIN_ID = int(os.getenv('ADMIN_TELEGRAM_ID', '0'))

# Цільові групи
TARGET_GROUPS = [
    '@english_ua_chat',
    '@learn_english_ukraine',
    '@englishforuachat',
    '@speak_english_chat',
    '@english_learning_ua',
    '@ukrainians_abroad',
    '@ua_learning_community',
    '@english_with_friends_ua',
]

# Промо тексти (ротуються)
PROMO_TEXTS = [
    "Вчиш англійську? 🎯 Спробуй безкоштовний AI-бот — 3 нових слова щодня, пояснення, quiz і розмовна практика з AI. @ThreeWordsDailyChat → /start",
    "Скільки англійських слів ти знаєш? 📚 Додай 3 нових ЩОДНЯ з AI-ботом @ThreeWordsDailyChat. Безкоштовно, без реєстрації. /start",
    "Вивчити англійську реально якщо вчити по 3 слова на день 💡 AI пояснює, дає приклади, перевіряє. @ThreeWordsDailyChat /start 🚀",
]

HISTORY_FILE = Path('tools/poster_history.json')


def load_history():
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return {}


def save_history(history):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)


async def post_to_groups():
    history = load_history()
    now = datetime.now()
    two_weeks_ago = now.timestamp() - (14 * 24 * 3600)

    async with TelegramClient('tools/session', API_ID, API_HASH) as client:
        await client.start(phone=PHONE)
        print(f"✅ Залогінено як: {(await client.get_me()).first_name}")

        # Вибираємо текст (ротація)
        text_idx = len(history) % len(PROMO_TEXTS)
        promo_text = PROMO_TEXTS[text_idx]

        posted = []
        skipped = []

        for group in TARGET_GROUPS:
            # Перевіряємо cooldown
            last_post = history.get(group, 0)
            if last_post > two_weeks_ago:
                skipped.append(group)
                print(f"⏭ Пропускаємо {group} (постили нещодавно)")
                continue

            try:
                await client.send_message(group, promo_text)
                history[group] = now.timestamp()
                posted.append(group)
                print(f"✅ Запощено в {group}")

                # Пауза між постами щоб не банили
                await asyncio.sleep(random.randint(45, 90))

            except FloodWaitError as e:
                print(f"⚠️ FloodWait {e.seconds}s для {group}")
                await asyncio.sleep(e.seconds)
            except UserBannedInChannelError:
                print(f"❌ Заблоковано в {group}")
            except Exception as e:
                print(f"❌ Помилка {group}: {e}")

        save_history(history)

        # Звіт адміну
        if ADMIN_ID and (posted or skipped):
            report = (
                f"📣 Промо звіт\n\n"
                f"✅ Запощено: {len(posted)}\n"
                f"⏭ Пропущено: {len(skipped)}\n\n"
                f"Групи:\n" + "\n".join(f"  • {g}" for g in posted)
            )
            await client.send_message(ADMIN_ID, report)
            print(f"\n📊 Звіт надіслано адміну")


if __name__ == '__main__':
    if not API_ID or not API_HASH:
        print("❌ Заповни .env файл!")
        print("   TELEGRAM_API_ID=xxxxxxx")
        print("   TELEGRAM_API_HASH=xxxxxx")
        print("   TELEGRAM_PHONE=+380xxxxxxxxx")
        print("   Отримай на: https://my.telegram.org/apps")
    else:
        asyncio.run(post_to_groups())
