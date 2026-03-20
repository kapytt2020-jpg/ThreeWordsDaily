"""
setup_botfather.py — Auto-configure all ThreeWordsDaily bots via Telegram Bot API.

Sets name, description, about text, and commands for each bot.

Usage:
    python3 setup_botfather.py

Requires .env with:
    LEARNING_BOT_TOKEN
    TEACHER_BOT_TOKEN
    ANALYST_BOT_TOKEN
    MARKETER_BOT_TOKEN
"""

import asyncio
import os
import aiohttp
from dotenv import load_dotenv

load_dotenv()

# ── Bot configs ────────────────────────────────────────────────────────────────

BOTS = [
    {
        "token_env": "LEARNING_BOT_TOKEN",
        "name": "ThreeWordsDaily",
        "description": "Щоденне вивчення англійської: 3 слова, квізи, стріки та компаньйон-петс 🐾",
        "short_description": "3 слова щодня. Квізи. Стріки. @ThreeWordsDailyChat",
        "commands": [
            ("word",    "Слово дня"),
            ("quiz",    "Квіз"),
            ("streak",  "Мій стрік"),
            ("pet",     "Мій петс"),
            ("top",     "Топ гравців"),
            ("profile", "Мій профіль"),
            ("help",    "Допомога"),
        ],
    },
    {
        "token_env": "TEACHER_BOT_TOKEN",
        "name": "Лекс | ThreeWordsDaily",
        "description": "Груповий асистент-вчитель у @ThreeWordsDailyChat. Відповідає на граматичні запитання.",
        "short_description": "Вчитель групи @ThreeWordsDailyChat",
        "commands": [
            ("help", "Що я вмію?"),
        ],
    },
    {
        "token_env": "ANALYST_BOT_TOKEN",
        "name": "Analytics | ThreeWordsDaily",
        "description": "Аналітик і стратег @ThreeWordsDailyChat. Збирає статистику та будує звіти.",
        "short_description": "Статистика та аналіз @ThreeWordsDailyChat",
        "commands": [
            ("stats",  "Статистика групи"),
            ("report", "Повний звіт"),
            ("help",   "Допомога"),
        ],
    },
    {
        "token_env": "MARKETER_BOT_TOKEN",
        "name": "Growth | ThreeWordsDaily",
        "description": "Онбординг і реферальна система @ThreeWordsDailyChat. Запрошує нових учасників.",
        "short_description": "Реферали та онбординг @ThreeWordsDailyChat",
        "commands": [
            ("start",  "Почати"),
            ("invite", "Моє реферальне посилання"),
            ("help",   "Допомога"),
        ],
    },
]

# ── Telegram API helpers ───────────────────────────────────────────────────────

BASE = "https://api.telegram.org/bot{token}/{method}"


async def tg(session: aiohttp.ClientSession, token: str, method: str, **payload) -> dict:
    url = BASE.format(token=token, method=method)
    async with session.post(url, json=payload) as r:
        return await r.json()


async def setup_bot(session: aiohttp.ClientSession, cfg: dict) -> None:
    token = os.getenv(cfg["token_env"], "")
    if not token:
        print(f"  ⚠️  {cfg['token_env']} not set — skipping")
        return

    label = cfg["name"]
    print(f"\n🤖 {label}")

    # Get current bot username for reference
    me = await tg(session, token, "getMe")
    if me.get("ok"):
        print(f"   @{me['result']['username']}")

    results = await asyncio.gather(
        tg(session, token, "setMyName",             name=cfg["name"]),
        tg(session, token, "setMyDescription",      description=cfg["description"]),
        tg(session, token, "setMyShortDescription", short_description=cfg["short_description"]),
        tg(session, token, "setMyCommands",         commands=[
            {"command": cmd, "description": desc}
            for cmd, desc in cfg["commands"]
        ]),
    )

    labels = ["setMyName", "setMyDescription", "setMyShortDescription", "setMyCommands"]
    for lbl, res in zip(labels, results):
        status = "✅" if res.get("ok") else f"❌ {res.get('description', '')}"
        print(f"   {lbl}: {status}")


async def main() -> None:
    print("ThreeWordsDaily — BotFather Setup")
    print("=" * 40)
    async with aiohttp.ClientSession() as session:
        for cfg in BOTS:
            await setup_bot(session, cfg)
    print("\n✅ Done!")


if __name__ == "__main__":
    asyncio.run(main())
