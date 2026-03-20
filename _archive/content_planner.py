"""
content_planner.py — AI планувальник контенту на тиждень
Запуск: python3 content_planner.py
Рекомендований запуск: кожну неділю о 23:00

Що робить:
1. Читає з Google Sheets які слова/теми були (used_words)
2. Аналізує що отримало реакції (analytics)
3. AI генерує план на наступний тиждень
4. Зберігає план в content_plan таблицю
5. Надсилає план адміну в Telegram
"""

import asyncio
import os
import json
from datetime import datetime, timedelta
from openai import AsyncOpenAI
import httpx
from dotenv import load_dotenv
load_dotenv()

# ======= НАЛАШТУВАННЯ =======
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "")

# Google Sheets (через Apps Script або Sheets API)
SHEETS_API_URL = os.getenv("SHEETS_API_URL", "")  # n8n webhook або Apps Script URL

openai = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def fetch_used_words(weeks_back: int = 4) -> list[str]:
    """Отримує слова які вже використовувались."""
    if not SHEETS_API_URL:
        # Заглушка для тестування
        return ["resilient", "thrive", "persistent", "overwhelmed", "consistent",
                "ambitious", "genuine", "eloquent", "diligent", "innovative"]
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{SHEETS_API_URL}/used_words?weeks={weeks_back}")
            data = resp.json()
            return [row["word"] for row in data.get("rows", [])]
    except Exception as e:
        print(f"⚠️ Не вдалось отримати used_words: {e}")
        return []


async def fetch_top_performing_content() -> str:
    """Отримує який контент отримав найбільше реакцій."""
    if not SHEETS_API_URL:
        return "Найкраще: quiz питання, idioms з гумором, слова про емоції та роботу"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{SHEETS_API_URL}/analytics/top_content")
            data = resp.json()
            return data.get("summary", "")
    except Exception as e:
        print(f"⚠️ Не вдалось отримати analytics: {e}")
        return ""


async def generate_weekly_plan(used_words: list[str], top_content: str) -> dict:
    """AI генерує контент-план на наступний тиждень."""
    next_monday = datetime.now() + timedelta(days=(7 - datetime.now().weekday()))
    week_dates = [(next_monday + timedelta(days=i)).strftime("%d.%m (%a)") for i in range(7)]

    used_str = ", ".join(used_words[-30:]) if used_words else "немає даних"

    resp = await openai.chat.completions.create(
        model="gpt-4",
        messages=[{
            "role": "system",
            "content": "Ти контент-менеджер для Telegram-бота з вивчення англійської. Відповідай тільки валідним JSON."
        }, {
            "role": "user",
            "content": f"""Склади контент-план для @ThreeWordsDailyChat на тиждень {week_dates[0]} - {week_dates[6]}.

Вже використані слова (не повторювати): {used_str}

Що працювало найкраще: {top_content or "quiz, idioms, практичні слова"}

Формат JSON:
{{
  "week": "{week_dates[0]} - {week_dates[6]}",
  "theme": "загальна тема тижня",
  "days": [
    {{
      "date": "{week_dates[0]}",
      "words": ["word1", "word2", "word3"],
      "category": "emotions/work/travel/relationships/etc",
      "idiom": "idiom дня",
      "story_hint": "про що mini-story ввечері"
    }}
  ],
  "friday_fact": "тема fun fact на п'ятницю",
  "sunday_quiz_focus": "на що наголосити в weekly quiz"
}}

Тільки JSON."""
        }],
        max_tokens=1500,
        temperature=0.7,
    )
    content = resp.choices[0].message.content.strip()
    return json.loads(content)


async def save_plan_to_sheets(plan: dict):
    """Зберігає план в Google Sheets."""
    if not SHEETS_API_URL:
        print("⚠️ SHEETS_API_URL не задано — план не збережено в Sheets")
        return
    try:
        async with httpx.AsyncClient() as client:
            await client.post(f"{SHEETS_API_URL}/content_plan", json=plan)
        print("✅ План збережено в Google Sheets")
    except Exception as e:
        print(f"❌ Помилка збереження: {e}")


async def send_plan_to_admin(plan: dict):
    """Надсилає план адміну в зручному форматі."""
    if not TELEGRAM_BOT_TOKEN or not ADMIN_CHAT_ID:
        print("⚠️ TELEGRAM_BOT_TOKEN або ADMIN_CHAT_ID не задано")
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return

    lines = [
        f"<b>📅 Контент-план: {plan['week']}</b>",
        f"🎯 Тема тижня: <i>{plan['theme']}</i>",
        "",
    ]

    for day in plan.get("days", []):
        words = " | ".join(f"<code>{w}</code>" for w in day["words"])
        lines.append(f"<b>{day['date']}</b> [{day['category']}]")
        lines.append(f"  📚 Слова: {words}")
        lines.append(f"  💬 Idiom: {day['idiom']}")
        lines.append(f"  📖 Story: {day['story_hint']}")
        lines.append("")

    lines.append(f"🤯 Fun fact п'ятниці: {plan.get('friday_fact', '—')}")
    lines.append(f"🏆 Quiz неділі: {plan.get('sunday_quiz_focus', '—')}")

    text = "\n".join(lines)

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={
            "chat_id": ADMIN_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
        })
    print("✅ План надіслано адміну")


async def run():
    print("🤖 Генерую контент-план на наступний тиждень...")

    used_words = await fetch_used_words()
    print(f"📋 Використано слів раніше: {len(used_words)}")

    top_content = await fetch_top_performing_content()

    plan = await generate_weekly_plan(used_words, top_content)
    print(f"✅ План згенеровано: тема '{plan.get('theme', '?')}'")

    await save_plan_to_sheets(plan)
    await send_plan_to_admin(plan)

    print("\n📅 ПЛАН:")
    for day in plan.get("days", []):
        print(f"  {day['date']}: {', '.join(day['words'])} [{day['category']}]")


if __name__ == "__main__":
    asyncio.run(run())
