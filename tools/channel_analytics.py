"""
Channel Analytics — Telethon
Аналізує конкурентів напряму через Telegram API
Дає реальні дані: підписники, охоплення, типи контенту
"""

import asyncio
import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.functions.channels import GetFullChannelRequest

load_dotenv()

API_ID = int(os.getenv('TELEGRAM_API_ID', '0'))
API_HASH = os.getenv('TELEGRAM_API_HASH', '')
PHONE = os.getenv('TELEGRAM_PHONE', '')

COMPETITORS = [
    'englishforukrainians',
    'greenforestschool',
    'cambridge_ua',
    'english_with_ann',
    'learn_english_ua',
]

OUR_CHANNEL = 'ThreeWordsDailyChat'


async def analyze_channel(client, username):
    try:
        entity = await client.get_entity(f'@{username}')
        full = await client(GetFullChannelRequest(entity))

        subscribers = full.full_chat.participants_count

        # Беремо останні 20 постів
        messages = await client.get_messages(entity, limit=20)

        views = [m.views or 0 for m in messages if m.views]
        avg_views = sum(views) // len(views) if views else 0
        er = round((avg_views / subscribers * 100), 2) if subscribers else 0

        # Типи контенту
        has_photo = any(m.photo for m in messages)
        has_video = any(m.video for m in messages)
        has_voice = any(m.voice for m in messages)
        has_poll = any(m.poll for m in messages)

        # Активність (пости за тиждень)
        week_ago = datetime.now() - timedelta(days=7)
        weekly_posts = sum(1 for m in messages if m.date.replace(tzinfo=None) > week_ago)

        return {
            'username': username,
            'subscribers': subscribers,
            'avg_views': avg_views,
            'engagement_rate': er,
            'weekly_posts': weekly_posts,
            'content': {
                'photo': has_photo,
                'video': has_video,
                'voice': has_voice,
                'poll': has_poll,
            },
            'checked_at': datetime.now().isoformat()
        }
    except Exception as e:
        return {'username': username, 'error': str(e)}


async def run_analysis():
    async with TelegramClient('tools/session', API_ID, API_HASH) as client:
        await client.start(phone=PHONE)
        print("🔍 Аналізую конкурентів...\n")

        results = []
        for username in COMPETITORS:
            print(f"  Аналізую @{username}...")
            data = await analyze_channel(client, username)
            results.append(data)
            await asyncio.sleep(2)

        # Наш канал
        print(f"  Аналізую наш @{OUR_CHANNEL}...")
        ours = await analyze_channel(client, OUR_CHANNEL)

        # Зберігаємо результати
        output = {
            'date': datetime.now().isoformat(),
            'our_channel': ours,
            'competitors': results
        }

        with open('tools/analytics_result.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        # Виводимо звіт
        print("\n" + "="*50)
        print("📊 АНАЛІЗ КОНКУРЕНТІВ")
        print("="*50)

        all_channels = sorted(results, key=lambda x: x.get('subscribers', 0), reverse=True)
        for c in all_channels:
            if 'error' not in c:
                print(f"\n@{c['username']}")
                print(f"  Підписники: {c['subscribers']:,}")
                print(f"  Середній охоп: {c['avg_views']:,}")
                print(f"  ER: {c['engagement_rate']}%")
                print(f"  Постів/тиждень: {c['weekly_posts']}")

        print(f"\n{'='*50}")
        print(f"НАШ КАНАЛ @{OUR_CHANNEL}")
        if 'error' not in ours:
            print(f"  Підписники: {ours.get('subscribers',0):,}")
            print(f"  ER: {ours.get('engagement_rate',0)}%")

        print("\n✅ Збережено в tools/analytics_result.json")


if __name__ == '__main__':
    asyncio.run(run_analysis())
