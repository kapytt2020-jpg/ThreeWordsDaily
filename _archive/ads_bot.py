"""
@Myadsformebot — рекламний бот
Відповідає на питання, веде людей в @ThreeWordsDailyChat
"""
import asyncio, json, logging
from pathlib import Path
from openai import AsyncOpenAI
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

_creds    = json.loads(Path("credentials.local.json").read_text())
TOKEN     = _creds["telegram_bots"]["Myadsformebot"]
OPENAI_KEY= _creds["openai_api_key"]
GROUP_LINK= "https://t.me/ThreeWordsDailyChat"

logging.basicConfig(format="%(asctime)s [AdsBot] %(message)s", level=logging.INFO)
ai = AsyncOpenAI(api_key=OPENAI_KEY)

SYSTEM = """Ти — помічник з вивчення англійської мови.
Відповідаєш коротко і завжди запрошуєш в групу @ThreeWordsDailyChat.
Відповідаєш українською. HTML теги. 2-3 речення максимум."""

KB = InlineKeyboardMarkup([[
    InlineKeyboardButton("📚 Вчити англійську безкоштовно", url=GROUP_LINK)
]])

async def ask(text):
    try:
        r = await ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":SYSTEM},{"role":"user","content":text}],
            max_tokens=200, temperature=0.7)
        return r.choices[0].message.content.strip()
    except:
        return f"Приєднуйся до нашої групи! 👉 {GROUP_LINK}"

async def cmd_start(update, ctx):
    if update.effective_chat.type != "private": return
    await update.message.reply_html(
        "👋 Привіт! Хочеш вчити англійську?\n\n"
        "Щодня нові слова + AI пояснення — безкоштовно! 🎯",
        reply_markup=KB)

async def handle_msg(update, ctx):
    if not update.message or not update.message.text or update.effective_user.is_bot: return
    if update.effective_chat.type != "private": return
    reply = await ask(update.message.text)
    await update.message.reply_html(reply, reply_markup=KB)

async def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    logging.info("✅ @Myadsformebot онлайн")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
