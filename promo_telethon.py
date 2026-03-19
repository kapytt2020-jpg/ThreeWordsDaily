"""
Промо-бот на Telethon — постить в групи від USER акаунту
Запуск: python3 promo_telethon.py

Перший запуск: введи номер телефону та код з Telegram
Далі сесія зберігається і він працює автоматично
"""

import asyncio
import random
from datetime import datetime
from telethon import TelegramClient
from telethon.errors import FloodWaitError, UserBannedInChannelError, ChatWriteForbiddenError

# ======= НАЛАШТУВАННЯ =======
API_ID = None      # Отримай на my.telegram.org → App API
API_HASH = None    # Отримай на my.telegram.org → App API
PHONE = None       # Твій номер телефону +380XXXXXXXXX

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
    """Хто ще застряг на A2 і ніяк не може рухатись далі? 😅

Знайшов безкоштовний бот який реально допомагає:
👉 @ThreeWordsDailyChat

3 нові слова щодня + AI пояснює і відповідає на питання
Спробуй /start""",

    """Скільки разів починав вчити англійську і кидав? 🙋

@ThreeWordsDailyChat — формат як Duolingo але в Telegram:
• 3 слова щодня (не перевантажує)
• AI бот відповідає на будь-які питання
• Streak система тримає мотивацію

/start і поїхали 🚀""",

    """Цікавий факт: 300 слів покривають 65% розмовної англійської

@ThreeWordsDailyChat допомагає вчити їх по 3 на день
+ AI бот для практики прямо в Telegram

Безкоштовно. /start 👇""",
]

# ======= КОД =======

async def post_to_groups():
    if not API_ID or not API_HASH or not PHONE:
        print("❌ Заповни API_ID, API_HASH і PHONE у файлі")
        print("Отримай на: https://my.telegram.org/apps")
        return

    client = TelegramClient('promo_session', API_ID, API_HASH)
    await client.start(phone=PHONE)
    print("✅ Підключено до Telegram")

    text = random.choice(PROMO_TEXTS)
    results = {'posted': 0, 'skipped': 0, 'errors': 0}

    for group in TARGET_GROUPS:
        try:
            await client.send_message(group, text)
            results['posted'] += 1
            print(f"✅ Відправлено в {group}")

            # Пауза між постами (30-60 сек) щоб не банили
            delay = random.randint(30, 60)
            print(f"⏳ Чекаю {delay} сек...")
            await asyncio.sleep(delay)

        except FloodWaitError as e:
            print(f"⚠️ FloodWait {group}: чекаю {e.seconds} сек")
            await asyncio.sleep(e.seconds)
            results['skipped'] += 1

        except (UserBannedInChannelError, ChatWriteForbiddenError):
            print(f"🚫 Немає доступу до {group}")
            results['skipped'] += 1

        except Exception as e:
            print(f"❌ Помилка {group}: {e}")
            results['errors'] += 1

    print(f"\n📊 Результат: {results['posted']} відправлено, "
          f"{results['skipped']} пропущено, {results['errors']} помилок")

    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(post_to_groups())
