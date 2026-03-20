"""
content_extra.py — додатковий щоденний контент для @ThreeWordsDailyChat
Запуск окремо або імпорт в основний бот.

Розклад:
  Ранок  09:00 — 3 слова (основний бот)
  День   13:00 — idiom дня (цей модуль)
  Вечір  19:00 — mini-story з словами тижня (цей модуль)
  Пт     17:00 — fun fact про англійську (цей модуль)
  Нд     18:00 — weekly quiz (цей модуль)
"""

import asyncio
import os
import json
import random
from datetime import datetime, timedelta
from openai import AsyncOpenAI
from dotenv import load_dotenv
load_dotenv()

# ======= НАЛАШТУВАННЯ =======
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "@ThreeWordsDailyChat")

# ======= КЛІЄНТИ =======
openai = AsyncOpenAI(api_key=OPENAI_API_KEY)

import httpx

async def send_telegram(text: str, parse_mode: str = "HTML"):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": parse_mode,
        })

# ======= КОНТЕНТ ГЕНЕРАТОРИ =======

async def generate_idiom_of_day() -> str:
    """Генерує idiom дня з поясненням і прикладом."""
    resp = await openai.chat.completions.create(
        model="gpt-4",
        messages=[{
            "role": "system",
            "content": "Ти вчитель англійської для українців рівня A2-B1. Пиши коротко і зрозуміло."
        }, {
            "role": "user",
            "content": """Дай один популярний англійський idiom.
Формат (HTML для Telegram):
<b>Idiom дня 💬</b>

<b>[idiom]</b>
🇺🇦 [переклад українською]

📖 <i>[пояснення 1-2 речення]</i>

💬 Приклад:
"[приклад речення англійською]"
<i>— [переклад прикладу]</i>

Тільки цей формат, нічого зайвого."""
        }],
        max_tokens=300,
        temperature=0.8,
    )
    return resp.choices[0].message.content.strip()


async def generate_mini_story(words: list[str] = None) -> str:
    """Генерує міні-розповідь з поточними словами тижня."""
    words_text = ", ".join(words) if words else "resilient, thrive, persistent"
    resp = await openai.chat.completions.create(
        model="gpt-4",
        messages=[{
            "role": "system",
            "content": "Ти вчитель англійської для українців рівня A2-B1."
        }, {
            "role": "user",
            "content": f"""Напиши міні-розповідь (3-5 речень) англійською з цими словами: {words_text}
Потім переклад українською.

Формат (HTML):
<b>Mini-story вечора 📖</b>

<i>[розповідь англійською, виділи слова жирним через <b>слово</b>]</i>

🇺🇦 <i>[переклад]</i>

Слова тижня: {words_text}"""
        }],
        max_tokens=400,
        temperature=0.9,
    )
    return resp.choices[0].message.content.strip()


async def generate_fun_fact() -> str:
    """П'ятниця — fun fact про англійську мову."""
    resp = await openai.chat.completions.create(
        model="gpt-4",
        messages=[{
            "role": "system",
            "content": "Ти вчитель англійської. Пиши цікаво і коротко."
        }, {
            "role": "user",
            "content": """Дай один цікавий факт про англійську мову якого більшість не знає.

Формат (HTML):
<b>Fun fact п'ятниці 🤯</b>

[факт 2-3 речення, цікаво і з гумором]

<i>#funfact #English</i>"""
        }],
        max_tokens=200,
        temperature=0.9,
    )
    return resp.choices[0].message.content.strip()


async def generate_weekly_quiz(words: list[str] = None) -> list[dict]:
    """Неділя — weekly quiz на 5 питань по словах тижня."""
    words_text = ", ".join(words) if words else "resilient, thrive, persistent, overwhelmed, consistent"
    resp = await openai.chat.completions.create(
        model="gpt-4",
        messages=[{
            "role": "system",
            "content": "Ти вчитель англійської. Повертай тільки валідний JSON."
        }, {
            "role": "user",
            "content": f"""Створи 5 питань quiz по цих словах: {words_text}

Повертай JSON масив:
[
  {{
    "question": "Що означає 'resilient'?",
    "answers": ["стійкий", "розслаблений", "радісний", "втомлений"],
    "correct": 0,
    "explanation": "Resilient = здатний відновлюватись після труднощів"
  }}
]

Тільки JSON, нічого зайвого."""
        }],
        max_tokens=800,
        temperature=0.5,
    )
    content = resp.choices[0].message.content.strip()
    return json.loads(content)


async def send_quiz_to_telegram(questions: list[dict]):
    """Відправляє weekly quiz як серію повідомлень з кнопками."""
    intro = "<b>Weekly Quiz 🏆</b>\n\nПеревір як запам'ятав слова тижня!\nВідповідай на 5 питань 👇"
    await send_telegram(intro)
    await asyncio.sleep(2)

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPoll"
    async with httpx.AsyncClient() as client:
        for i, q in enumerate(questions, 1):
            payload = {
                "chat_id": TELEGRAM_CHAT_ID,
                "question": f"{i}/5 — {q['question']}",
                "options": q["answers"],
                "type": "quiz",
                "correct_option_id": q["correct"],
                "explanation": q["explanation"],
                "is_anonymous": True,
            }
            await client.post(url, json=payload)
            await asyncio.sleep(3)


# ======= ОСНОВНИЙ ЗАПУСК =======

async def run_by_schedule():
    """Запускає потрібний контент залежно від часу."""
    now = datetime.now()
    hour = now.hour
    weekday = now.weekday()  # 0=Mon, 4=Fri, 6=Sun

    # Приклад слів тижня (в реальному боті братись з Google Sheets)
    words_of_week = ["resilient", "thrive", "persistent", "overwhelmed", "consistent",
                     "ambitious", "genuine"]

    if hour == 13:
        print("📤 Відправляю idiom дня...")
        text = await generate_idiom_of_day()
        await send_telegram(text)

    elif hour == 19:
        print("📤 Відправляю mini-story...")
        text = await generate_mini_story(words_of_week[:5])
        await send_telegram(text)

    elif hour == 17 and weekday == 4:  # П'ятниця
        print("📤 Відправляю fun fact...")
        text = await generate_fun_fact()
        await send_telegram(text)

    elif hour == 18 and weekday == 6:  # Неділя
        print("📤 Відправляю weekly quiz...")
        questions = await generate_weekly_quiz(words_of_week)
        await send_quiz_to_telegram(questions)

    else:
        print(f"⏰ Зараз {hour}:00, нічого не відправляю")


if __name__ == "__main__":
    asyncio.run(run_by_schedule())
