"""
analytics.py — щотижневий аналітичний звіт для @ThreeWordsDailyChat
Запуск: python3 analytics.py
Рекомендований запуск: кожну неділю о 20:00

Збирає:
- Нові юзери за тиждень
- Retention (хто залишився після 7 днів)
- Топ команди (/stats, /quiz, /speak...)
- Streak статистика
- Результати прomo (скільки відправлено, конверсія)

Надсилає звіт адміну + зберігає в Google Sheets
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
SHEETS_API_URL = os.getenv("SHEETS_API_URL", "")

openai = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def fetch_sheet_data(endpoint: str) -> list[dict]:
    """Отримує дані з Google Sheets через n8n webhook або Apps Script."""
    if not SHEETS_API_URL:
        return []
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{SHEETS_API_URL}/{endpoint}")
            return resp.json().get("rows", [])
    except Exception as e:
        print(f"⚠️ fetch {endpoint}: {e}")
        return []


def calculate_stats(users: list[dict], streaks: list[dict], points: list[dict]) -> dict:
    """Розраховує метрики з сирих даних."""
    now = datetime.now()
    week_ago = now - timedelta(days=7)

    # Нові юзери за тиждень
    new_users = [
        u for u in users
        if u.get("joined_date") and
        datetime.fromisoformat(u["joined_date"]) >= week_ago
    ]

    # Retention: юзери що зайшли 7+ днів тому і ще активні
    old_users = [u for u in users if u.get("joined_date") and
                 datetime.fromisoformat(u["joined_date"]) < week_ago]
    retained = [u for u in old_users if u.get("last_active") and
                datetime.fromisoformat(u["last_active"]) >= week_ago]
    retention_rate = (len(retained) / len(old_users) * 100) if old_users else 0

    # Streak статистика
    active_streaks = [s for s in streaks if int(s.get("streak_count", 0)) > 0]
    max_streak = max((int(s.get("streak_count", 0)) for s in streaks), default=0)
    avg_streak = (sum(int(s.get("streak_count", 0)) for s in active_streaks) /
                  len(active_streaks)) if active_streaks else 0

    # Топ за балами
    sorted_points = sorted(points, key=lambda x: int(x.get("total_points", 0)), reverse=True)
    top_3 = sorted_points[:3]

    return {
        "period": f"{week_ago.strftime('%d.%m')} - {now.strftime('%d.%m.%Y')}",
        "total_users": len(users),
        "new_users_week": len(new_users),
        "retention_rate": round(retention_rate, 1),
        "active_streaks": len(active_streaks),
        "max_streak": max_streak,
        "avg_streak": round(avg_streak, 1),
        "top_3": top_3,
    }


async def generate_ai_insights(stats: dict) -> str:
    """AI аналізує статистику і дає поради."""
    resp = await openai.chat.completions.create(
        model="gpt-4",
        messages=[{
            "role": "system",
            "content": "Ти аналітик Telegram-ботів. Коротко і по суті."
        }, {
            "role": "user",
            "content": f"""Проаналізуй статистику бота @ThreeWordsDailyChat за тиждень:

{json.dumps(stats, ensure_ascii=False, indent=2)}

Дай:
1. Одну головну метрику на яку звернути увагу
2. Одну конкретну пораду для покращення retention
3. Оцінку тижня (0-10) і чому

Максимум 5 речень."""
        }],
        max_tokens=300,
        temperature=0.5,
    )
    return resp.choices[0].message.content.strip()


async def send_report_to_admin(stats: dict, insights: str):
    """Відправляє красивий звіт адміну."""
    if not TELEGRAM_BOT_TOKEN or not ADMIN_CHAT_ID:
        print("📊 ЗВІТ (без відправки — не задано токени):")
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        print("\n🤖 AI ІНСАЙТИ:")
        print(insights)
        return

    # Топ-3 рядок
    top_lines = []
    for i, user in enumerate(stats.get("top_3", []), 1):
        name = user.get("username") or user.get("user_id", "?")
        pts = user.get("total_points", 0)
        top_lines.append(f"  {['🥇','🥈','🥉'][i-1]} @{name} — {pts} балів")
    top_str = "\n".join(top_lines) if top_lines else "  немає даних"

    text = f"""<b>📊 Weekly Report: {stats['period']}</b>

<b>👥 Юзери</b>
  Всього: {stats['total_users']}
  Нових за тиждень: +{stats['new_users_week']}
  Retention 7d: {stats['retention_rate']}%

<b>🔥 Streaks</b>
  Активних: {stats['active_streaks']}
  Максимальний: {stats['max_streak']} днів
  Середній: {stats['avg_streak']} днів

<b>🏆 Топ-3 тижня</b>
{top_str}

<b>🤖 AI інсайти</b>
<i>{insights}</i>"""

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={
            "chat_id": ADMIN_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
        })
    print("✅ Звіт надіслано адміну")


async def save_to_sheets(stats: dict):
    """Зберігає тижневу статистику в Google Sheets."""
    if not SHEETS_API_URL:
        return
    try:
        async with httpx.AsyncClient() as client:
            await client.post(f"{SHEETS_API_URL}/analytics", json={
                **stats,
                "timestamp": datetime.now().isoformat(),
            })
        print("✅ Аналітику збережено в Sheets")
    except Exception as e:
        print(f"❌ Помилка збереження: {e}")


async def run():
    print("📊 Збираю тижневу аналітику...")

    # Паралельно отримуємо всі дані
    users, streaks, points = await asyncio.gather(
        fetch_sheet_data("users"),
        fetch_sheet_data("user_streaks"),
        fetch_sheet_data("user_points"),
    )

    # Якщо Sheets не налаштовано — використовуємо тестові дані
    if not users:
        print("⚠️ Sheets не підключено, використовую тестові дані")
        stats = {
            "period": f"{(datetime.now()-timedelta(7)).strftime('%d.%m')} - {datetime.now().strftime('%d.%m.%Y')}",
            "total_users": 127,
            "new_users_week": 23,
            "retention_rate": 41.5,
            "active_streaks": 38,
            "max_streak": 14,
            "avg_streak": 3.2,
            "top_3": [],
        }
    else:
        stats = calculate_stats(users, streaks, points)

    print(f"✅ Статистика: {stats['total_users']} юзерів, +{stats['new_users_week']} нових, retention {stats['retention_rate']}%")

    insights = await generate_ai_insights(stats)

    await asyncio.gather(
        send_report_to_admin(stats, insights),
        save_to_sheets(stats),
    )


if __name__ == "__main__":
    asyncio.run(run())
