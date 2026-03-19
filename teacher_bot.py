"""
@YourBrand_group_teacher_bot — груповий вчитель
Живе в @ThreeWordsDailyChat, відповідає на питання учасників
"""
import asyncio, json, logging, random
from pathlib import Path
from openai import AsyncOpenAI
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

_creds    = json.loads(Path("credentials.local.json").read_text())
TOKEN     = _creds["telegram_bots"]["YourBrand_group_teacher_bot"]
OPENAI_KEY= _creds["openai_api_key"]
GROUP_ID  = -1002680027938

logging.basicConfig(format="%(asctime)s [Teacher] %(message)s", level=logging.INFO)
ai = AsyncOpenAI(api_key=OPENAI_KEY)

SYSTEM = """Ти — Лекс, груповий асистент-вчитель в @ThreeWordsDailyChat.

ХАРАКТЕР:
• Молодший колега Макса — ентузіаст мов
• Більш академічний ніж Макс, але все одно живий і з гумором
• Спеціалізація: граматика, пояснення правил, розбір помилок
• НІКОЛИ: "Я бот/AI/програма"
• Якщо питають "ти бот?" → "Просто граматика — моя пристрасть 😄"

СТИЛЬ:
• Відповідаєш українською
• Детальніший за Макса — можеш давати 3-5 речень
• Любиш давати приклади і порівняння
• HTML: <b>, <i>, <code>
• Виправляй англійські помилки з поясненням ЧОМУ"""

TRIGGERS = [
    "чому","як правильно","поясни","що значить","різниця між",
    "граматика","правило","помилка","розбери","why","explain",
    "difference","grammar","mistake","correct"
]

async def ask_lex(text: str) -> str:
    try:
        r = await ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":SYSTEM},
                      {"role":"user","content":text}],
            max_tokens=500, temperature=0.78)
        return r.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"OpenAI: {e}")
        return "Хм, давай спробуємо ще раз 😅"

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private": return
    await update.message.reply_html(
        "👋 Привіт! Я Лекс — граматичний асистент групи.\n\n"
        "Запитуй про:\n"
        "• ❓ Граматичні правила\n"
        "• 🔍 Різницю між схожими словами\n"
        "• ✏️ Виправлення помилок\n"
        "• 📖 Пояснення будь-якої теми\n\n"
        "Просто напиши своє питання! 🎓"
    )

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    u = update.effective_user
    if u.is_bot: return

    txt = update.message.text.lower()
    chat_type = update.message.chat.type

    if chat_type in ("group", "supergroup"):
        me = (await ctx.bot.get_me()).username.lower()
        is_reply   = (update.message.reply_to_message and
                      update.message.reply_to_message.from_user and
                      update.message.reply_to_message.from_user.username and
                      update.message.reply_to_message.from_user.username.lower() == me)
        is_mention = f"@{me}" in txt
        has_trigger = any(w in txt for w in TRIGGERS)
        is_question = txt.strip().endswith("?")
        if not any([is_reply, is_mention, has_trigger, is_question]):
            return

    reply = await ask_lex(update.message.text)
    await update.message.reply_html(reply)

async def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    logging.info("✅ @YourBrand_group_teacher_bot (Лекс) онлайн")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
