"""
Автономний промо-агент — постить в групи двічі на день
Розклад: 10:00 і 17:00 (Kyiv time)
Звітує адміну через @Clickecombot
"""
import asyncio, random, json, logging
from datetime import datetime, date
from pathlib import Path
from telethon import TelegramClient
from telethon.errors import FloodWaitError, UserBannedInChannelError, ChatWriteForbiddenError

logging.basicConfig(format="%(asctime)s [Promo] %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

# ─── CONFIG ────────────────────────────────────────────────
API_ID   = 39641928
API_HASH = 'a2618c2bda0c4b346de9af6d6fbfc640'
PHONE    = '+380982896457'
ADMIN_ID = 1371213874

_creds     = json.loads(Path("credentials.local.json").read_text())
BOT_TOKEN  = _creds["telegram_bots"]["Clickecombot"]

# Перевірені групи (де вже є доступ)
TARGET_GROUPS = [
    '@ukrainians_us',
    '@breakfast_english',
    '@ChatUkraineUK',
    '@knlu_chat',
]

# Розширені промо тексти (більше варіантів = менше спаму)
PROMO_TEXTS = [
    """Хто ще застряг на A2 і ніяк не може рухатись далі? 😅

Знайшов безкоштовний бот який реально допомагає:
👉 @ThreeWordsDailyChat

3 нові слова щодня + AI пояснює і відповідає на питання
Спробуй /start""",

    """Скільки разів починав вчити англійську і кидав? 🙋

@ThreeWordsDailyChat — формат як Duolingo але в Telegram:
• Слова щодня (не перевантажує)
• AI бот відповідає на будь-які питання
• Streak система тримає мотивацію

/start і поїхали 🚀""",

    """Цікавий факт: 300 слів покривають 65% розмовної англійської 🧠

@ThreeWordsDailyChat допомагає вчити їх системно
+ AI для практики прямо в Telegram

Безкоштовно. /start 👇""",

    """Як швидко підтягнути англійську без зубріння?

В @ThreeWordsDailyChat щодня:
⏰ 9:00 — нове слово з поясненням
🧠 11:00 — quiz
💬 Завжди можна запитати AI

Вже 100+ учасників. Приходь! 👉""",

    """English practice щодня — без нудних підручників 📚

@ThreeWordsDailyChat:
✅ Слово + правило щодня
✅ AI відповідає на будь-яке питання
✅ Граматика, ідіоми, вимова
✅ Безкоштовно

Спробуй: /start""",
]

# ─── NOTIFY ADMIN ──────────────────────────────────────────
async def notify_admin(text: str):
    """Відправляє повідомлення адміну через Bot API"""
    try:
        import httpx
        async with httpx.AsyncClient() as http:
            await http.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={"chat_id": ADMIN_ID, "text": text, "parse_mode": "HTML"}
            )
    except Exception as e:
        log.error(f"notify_admin: {e}")

# ─── PROMO POSTING ─────────────────────────────────────────
async def run_promo():
    log.info("🚀 Починаємо промо-розсилку")
    results = {"posted": 0, "skipped": 0, "errors": 0, "groups": []}

    try:
        client = TelegramClient("promo_session", API_ID, API_HASH)
        await client.connect()

        if not await client.is_user_authorized():
            log.error("❌ Telethon сесія не авторизована. Запусти python3 promo_telethon.py один раз вручну")
            await notify_admin("❌ <b>Promo agent:</b> сесія не авторизована!\nЗапусти вручну: <code>python3 promo_telethon.py</code>")
            await client.disconnect()
            return

        text = random.choice(PROMO_TEXTS)

        for group in TARGET_GROUPS:
            try:
                await client.send_message(group, text)
                results["posted"] += 1
                results["groups"].append(f"✅ {group}")
                log.info(f"✅ {group}")
                delay = random.randint(45, 90)
                log.info(f"⏳ Пауза {delay}с")
                await asyncio.sleep(delay)

            except FloodWaitError as e:
                log.warning(f"FloodWait {group}: {e.seconds}с")
                results["skipped"] += 1
                results["groups"].append(f"⏳ {group} (flood {e.seconds}с)")
                await asyncio.sleep(min(e.seconds, 120))

            except (UserBannedInChannelError, ChatWriteForbiddenError):
                results["skipped"] += 1
                results["groups"].append(f"🚫 {group}")
                log.warning(f"Немає доступу: {group}")

            except Exception as e:
                results["errors"] += 1
                results["groups"].append(f"❌ {group}: {e}")
                log.error(f"Помилка {group}: {e}")

        await client.disconnect()

    except Exception as e:
        log.error(f"Promo run failed: {e}")
        await notify_admin(f"❌ <b>Promo agent crashed:</b> {e}")
        return

    # Звіт адміну
    groups_str = "\n".join(results["groups"])
    report = (
        f"📢 <b>Промо-звіт {datetime.now().strftime('%H:%M %d.%m')}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"✅ Відправлено: {results['posted']}\n"
        f"⏭ Пропущено: {results['skipped']}\n"
        f"❌ Помилок: {results['errors']}\n\n"
        f"{groups_str}"
    )
    await notify_admin(report)
    log.info(f"📊 Готово: {results['posted']} відправлено")

# ─── SCHEDULER ─────────────────────────────────────────────
async def main():
    log.info("✅ Auto-promo agent запущено | 10:00 / 17:00")
    done_today = set()

    while True:
        now  = datetime.now()
        h, m = now.hour, now.minute
        day  = str(now.date())

        for target_h, key in [(10, "am"), (17, "pm")]:
            tag = f"{key}_{day}"
            if h == target_h and m < 5 and tag not in done_today:
                done_today.add(tag)
                await run_promo()

        # скидаємо опівночі
        if h == 0 and m == 0:
            done_today.clear()

        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
