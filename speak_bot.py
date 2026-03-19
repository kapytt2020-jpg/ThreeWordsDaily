"""
@SpeakBetterrbot — PR бот
Відповідає на питання про групу, просуває @ThreeWordsDailyChat
Запускається автоматично через launchd
"""
import asyncio, json, logging
from pathlib import Path
from openai import AsyncOpenAI
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

_creds    = json.loads(Path("credentials.local.json").read_text())
TOKEN     = _creds["telegram_bots"]["SpeakBetterrbot"]
OPENAI_KEY= _creds["openai_api_key"]
GROUP_LINK= "https://t.me/ThreeWordsDailyChat"

logging.basicConfig(format="%(asctime)s [SpeakBot] %(message)s", level=logging.INFO)
ai = AsyncOpenAI(api_key=OPENAI_KEY)

SYSTEM = f"""Ти — Макс, представник групи @ThreeWordsDailyChat для вивчення англійської.

МЕТА: залучати нових учасників в групу.

ПРАВИЛА:
• Завжди дружній, позитивний, з ентузіазмом
• Відповідаєш українською
• На будь-яке питання про англійську — коротко відповідаєш І запрошуєш в групу
• Завжди закінчуй запрошенням: "Приєднуйся до @ThreeWordsDailyChat — щодня нові слова і практика! 🚀"
• НІКОЛИ не кажи що ти бот або AI
• HTML теги: <b>, <i>, <code>
• Коротко: 2-4 речення"""

async def ask(text: str) -> str:
    try:
        r = await ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":SYSTEM},{"role":"user","content":text}],
            max_tokens=300, temperature=0.8)
        return r.choices[0].message.content.strip()
    except:
        return f"Привіт! Вчи англійську разом з нами 👉 {GROUP_LINK} 🚀"

KB = InlineKeyboardMarkup([[
    InlineKeyboardButton("🚀 Приєднатись до групи", url=GROUP_LINK)
]])

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private": return
    await update.message.reply_html(
        "👋 <b>Привіт!</b>\n\n"
        "Я допомагаю з вивченням англійської 😊\n\n"
        "🎯 Щодня нові слова, граматика і практика — все безкоштовно!\n\n"
        "Приєднуйся до нашої спільноти 👇",
        reply_markup=KB
    )

async def handle_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    if update.effective_user.is_bot: return
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
    logging.info("✅ @SpeakBetterrbot онлайн")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
