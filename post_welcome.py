"""
post_welcome.py — One-shot welcome message to Voodoo Telegram group.
Run once: python3 post_welcome.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import aiohttp
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN         = os.getenv("VOODOO_OPS_BOT_TOKEN", "")
INTERNAL_GROUP_ID = int(os.getenv("INTERNAL_GROUP_ID", "0"))
STATE_FILE        = Path(__file__).parent / "group_state.json"
API_BASE          = f"https://api.telegram.org/bot{BOT_TOKEN}"


def get_content_thread_id() -> int:
    if STATE_FILE.exists():
        data = json.loads(STATE_FILE.read_text())
        topic_ids = data.get("topic_ids", {})
        return topic_ids.get("📢 Content", 68)
    return 68  # fallback


WELCOME_MESSAGE = """🎉 <b>Ласкаво просимо до Voodoo English Platform!</b>

Привіт, команда! 👋

Цей канал — ваш щоденний простір для навчання, практики та зростання в англійській мові.

━━━━━━━━━━━━━━━━━━

📅 <b>Щоденний розклад контенту</b>

🌅 <b>09:00</b> — 📖 <b>Word of the Day</b>
Нове слово з IPA вимовою, перекладом та прикладом речення. Вивчай по одному слову щодня — за рік матимеш 365 нових слів у словнику!

☀️ <b>13:00</b> — 🧠 <b>Fun English Fact</b>
Цікаві факти про англійську мову, етимологію та лінгвістику. Розширюй розуміння мови, а не лише лексику.

🌆 <b>18:00</b> — 🧪 <b>Mini Quiz</b>
Щоденний тест-опитування в форматі вікторини. Перевір свої знання та порівняй з командою!

🌙 <b>21:00</b> — 💫 <b>Daily Motivation</b>
Мотиваційна цитата для підтримки навчального настрою. Навчання мови — це марафон, а не спринт.

━━━━━━━━━━━━━━━━━━

🗂 <b>Теми цього каналу</b>

📊 <b>Analysis</b> — аналітика платформи та метрики
📢 <b>Content</b> — розклад та контент-план
📈 <b>Growth</b> — зростання та маркетинг
🛡 <b>Ops</b> — операційні звіти
📚 <b>Teaching</b> — навчальний контент (слова, мотивація)
🔊 <b>Speaking</b> — практика розмови
🧪 <b>Testing</b> — квізи та тести
🤖 <b>Agent-Talk</b> — AI агенти в роботі
🚀 <b>Deployments</b> — оновлення платформи
⚠️ <b>Alerts</b> — системні сповіщення

━━━━━━━━━━━━━━━━━━

🚀 <b>Платформа запущена та готова до роботи!</b>

Перший контент з'явиться вже сьогодні. Підписуйтесь на теми, які вас цікавлять.

<i>Voodoo English Platform — навчайся щодня, зростай щотижня.</i> ✨"""


async def post_welcome():
    if not BOT_TOKEN:
        print("ERROR: VOODOO_OPS_BOT_TOKEN not set")
        sys.exit(1)
    if not INTERNAL_GROUP_ID:
        print("ERROR: INTERNAL_GROUP_ID not set")
        sys.exit(1)

    thread_id = get_content_thread_id()
    print(f"Posting to group {INTERNAL_GROUP_ID}, thread {thread_id} (📢 Content)...")

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{API_BASE}/sendMessage",
            json={
                "chat_id": INTERNAL_GROUP_ID,
                "message_thread_id": thread_id,
                "text": WELCOME_MESSAGE,
                "parse_mode": "HTML",
            },
            timeout=aiohttp.ClientTimeout(total=15),
        ) as r:
            data = await r.json()
            if data.get("ok"):
                msg_id = data["result"]["message_id"]
                print(f"✅ Welcome message posted! message_id={msg_id}")
            else:
                print(f"❌ Failed: {data.get('description', data)}")
                sys.exit(1)


if __name__ == "__main__":
    asyncio.run(post_welcome())
