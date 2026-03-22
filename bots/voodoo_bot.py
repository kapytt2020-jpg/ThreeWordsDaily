"""
bots/voodoo_bot.py — VoodooBot (@v00dooBot)

Main public-facing bot. Handles onboarding, commands, and mini app entry.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timedelta

from dotenv import load_dotenv
from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Update,
    WebAppInfo,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)

from database import db

load_dotenv()

logging.basicConfig(
    format="%(asctime)s [voodoo_bot] %(levelname)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("voodoo_bot")

TOKEN       = os.getenv("VOODOO_BOT_TOKEN", "")
ADMIN_ID    = int(os.getenv("ADMIN_CHAT_ID", "0"))
MINIAPP_URL = os.getenv("MINIAPP_URL", "https://your-domain.com")

if not TOKEN:
    raise RuntimeError("VOODOO_BOT_TOKEN not set")


# ── Keyboards ─────────────────────────────────────────────────────────────────

def kb_main():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎮 Грати", web_app=WebAppInfo(url=MINIAPP_URL)),
            InlineKeyboardButton("📚 Урок", callback_data="lesson"),
        ],
        [
            InlineKeyboardButton("🏆 Рейтинг", callback_data="leaderboard"),
            InlineKeyboardButton("👤 Профіль", callback_data="profile"),
        ],
        [InlineKeyboardButton("📖 Слово дня", callback_data="word_of_day")],
    ])


def kb_level():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌱 Beginner (A1-A2)", callback_data="level_A2")],
        [InlineKeyboardButton("📗 Elementary (B1)",  callback_data="level_B1")],
        [InlineKeyboardButton("📘 Intermediate (B2)", callback_data="level_B2")],
        [InlineKeyboardButton("📙 Advanced (C1+)",    callback_data="level_C1")],
    ])


# ── XP / Rank helpers ─────────────────────────────────────────────────────────

def xp_to_rank(xp: int) -> str:
    if xp < 100:  return "🌱 Beginner"
    if xp < 300:  return "📗 Learner"
    if xp < 600:  return "📘 Student"
    if xp < 1000: return "📙 Practitioner"
    if xp < 2000: return "🎓 Scholar"
    return "⭐ Master"


def xp_bar(xp: int, width: int = 8) -> str:
    thresholds = [100, 300, 600, 1000, 2000, 5000]
    for t in thresholds:
        if xp < t:
            filled = round((xp / t) * width)
            return "█" * filled + "░" * (width - filled) + f" {xp}/{t}"
    return "█" * width + f" {xp} MAX"


# ── Handlers ──────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return

    u = await db.get_user(user.id, user.first_name or "", user.username or "")

    # Referral via deep link
    args = ctx.args or []
    if args and args[0].startswith("ref_"):
        try:
            ref_id = int(args[0][4:])
            if ref_id != user.id and not u.get("referrer_id"):
                await db.update_user(user.id, referrer_id=ref_id)
                # Reward referrer
                ref = await db.get_user(ref_id)
                new_xp = (ref.get("xp") or 0) + 50
                await db.update_user(ref_id, xp=new_xp, referral_count=(ref.get("referral_count") or 0) + 1)
                try:
                    await ctx.bot.send_message(ref_id,
                        f"🎉 Новий учень прийшов по твоєму запрошенню!\n+50 XP тобі!")
                except Exception:
                    pass
        except ValueError:
            pass

    if not u.get("level"):
        # New user — onboarding
        await update.message.reply_html(
            f"👋 Привіт, <b>{user.first_name}</b>!\n\n"
            "Я — <b>Voodoo</b> 🪄 — твій AI-вчитель англійської.\n\n"
            "Щодня:\n"
            "• 3 нових слова з вимовою\n"
            "• Ідіоми і міні-історії\n"
            "• Ігри, XP, серії та лідерборд\n"
            "• Tamagotchi-пет що росте разом з тобою\n\n"
            "<b>Який рівень англійської?</b>",
            reply_markup=kb_level(),
        )
    else:
        xp     = u.get("xp", 0)
        streak = u.get("streak", 0)
        await update.message.reply_html(
            f"👋 З поверненням, <b>{user.first_name}</b>!\n\n"
            f"{xp_to_rank(xp)}\n"
            f"⭐ {xp_bar(xp)}\n"
            f"🔥 Серія: {streak} дн.\n\n"
            "Готовий вчитися? 👇",
            reply_markup=kb_main(),
        )


async def cb_level(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    level = query.data.replace("level_", "")
    user  = update.effective_user
    await db.update_user(user.id, level=level)
    await query.edit_message_text(
        f"✅ Рівень встановлено: <b>{level}</b>\n\n"
        "Ти в грі! Починай свій перший урок 👇\n\n"
        "• /word — Слово дня\n"
        "• /quiz — Квіз\n"
        "• /lessons — Урок",
        parse_mode="HTML",
        reply_markup=kb_main(),
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_html(
        "🪄 <b>Voodoo — команди</b>\n\n"
        "<b>📚 Навчання</b>\n"
        "/word — слово дня\n"
        "/quiz — квіз\n"
        "/lessons — урок дня\n\n"
        "<b>📊 Прогрес</b>\n"
        "/stats — твоя статистика\n"
        "/streak — серія та заморозка\n"
        "/profile — профіль\n\n"
        "<b>🎮 Розваги</b>\n"
        "/play — відкрити Mini App\n"
        "/leaderboard — топ гравців\n\n"
        "<b>💎 Преміум</b>\n"
        "/subscribe — Voodoo Premium\n"
        "/freeze — заморожувач серії (15 ⭐)\n\n"
        "<b>👥 Спільнота</b>\n"
        "/invite — запросити друга (+50 XP)\n",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🎮 Відкрити Voodoo App",
                                 web_app=WebAppInfo(url=MINIAPP_URL)),
        ]]),
    )


async def cmd_word(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    u    = await db.get_user(user.id)

    # Try to get a word from DB
    conn = db._connect()
    word_row = conn.execute(
        "SELECT * FROM words ORDER BY RANDOM() LIMIT 1"
    ).fetchone()
    conn.close()

    if word_row:
        w = dict(word_row)
        ipa = f" [{w['ipa']}]" if w.get("ipa") else ""
        example = f"\n\n💬 <i>{w.get('example_en','')}</i>" if w.get("example_en") else ""
        ua_example = f"\n<i>{w.get('example_ua','')}</i>" if w.get("example_ua") else ""

        await update.message.reply_html(
            f"📖 <b>Слово дня</b>\n\n"
            f"<b>{w['word']}</b>{ipa}\n"
            f"🇺🇦 <b>{w['translation']}</b>"
            f"{example}{ua_example}\n\n"
            f"🏷 Рівень: {w.get('level','?')} | Тема: {w.get('theme','?')}",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🔊 Вимова", callback_data=f"pronounce_{w['id']}"),
                    InlineKeyboardButton("✅ Знаю!", callback_data=f"know_{w['id']}"),
                ],
                [InlineKeyboardButton("➡️ Наступне", callback_data="next_word")],
            ]),
        )
    else:
        await update.message.reply_text(
            "📖 Слова ще завантажуються!\n"
            "Поки відкрий Mini App для повного уроку 👇",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🎮 Voodoo App",
                                     web_app=WebAppInfo(url=MINIAPP_URL)),
            ]]),
        )


async def cmd_quiz(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    conn = db._connect()
    words = conn.execute("SELECT * FROM words ORDER BY RANDOM() LIMIT 4").fetchall()
    conn.close()

    if len(words) < 4:
        await update.message.reply_text(
            "Квіз доступний після завантаження слів.\n"
            "Відкрий Mini App для квізів! 🎮",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🎮 Квіз у додатку",
                                     web_app=WebAppInfo(url=MINIAPP_URL)),
            ]]),
        )
        return

    correct = dict(words[0])
    options = [dict(w)["translation"] for w in words]
    import random; random.shuffle(options)

    kb = [[InlineKeyboardButton(opt, callback_data=f"quiz_{opt}_{correct['translation']}")] for opt in options]
    await update.message.reply_html(
        f"❓ <b>Квіз</b>\n\n"
        f"Що означає: <b>{correct['word']}</b>?",
        reply_markup=InlineKeyboardMarkup(kb),
    )


async def cb_quiz(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    _, chosen, correct = query.data.split("_", 2)
    user = update.effective_user
    if chosen == correct:
        await db.update_user(user.id,
            xp=(await db.get_user(user.id)).get("xp", 0) + 10,
            correct_answers=(await db.get_user(user.id)).get("correct_answers", 0) + 1
        )
        await query.edit_message_text(f"✅ Правильно! +10 XP\n\nВідповідь: {correct}")
    else:
        await query.edit_message_text(f"❌ Неправильно.\n\nПравильна відповідь: {correct}")


async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    u    = await db.get_user(user.id)
    xp     = u.get("xp", 0)
    streak = u.get("streak", 0)
    words  = u.get("total_words", 0)
    correct = u.get("correct_answers", 0)
    wrong   = u.get("wrong_answers", 0)
    total   = correct + wrong
    acc = round(correct / total * 100, 1) if total else 0

    await update.message.reply_html(
        f"📊 <b>Твоя статистика</b>\n\n"
        f"{xp_to_rank(xp)}\n"
        f"⭐ XP: <b>{xp}</b>  {xp_bar(xp)}\n"
        f"🔥 Серія: <b>{streak} дн.</b>\n"
        f"📖 Слів: <b>{words}</b>\n"
        f"🎯 Точність: <b>{acc}%</b> ({correct}/{total})\n"
        f"💎 Рівень: <b>{u.get('level','?')}</b>",
    )


async def cmd_profile(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    u    = await db.get_user(user.id)
    bot_link = f"https://t.me/v00dooBot?start=ref_{user.id}"

    await update.message.reply_html(
        f"👤 <b>{user.first_name}</b>\n"
        f"@{user.username or '—'}\n\n"
        f"⭐ XP: {u.get('xp',0)}\n"
        f"🔥 Серія: {u.get('streak',0)} дн.\n"
        f"📖 Слів: {u.get('total_words',0)}\n"
        f"👥 Запрошено: {u.get('referral_count',0)}\n\n"
        f"🔗 Твоє посилання:\n<code>{bot_link}</code>",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🎮 Відкрити App",
                                 web_app=WebAppInfo(url=MINIAPP_URL)),
        ]]),
    )


async def cmd_invite(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    link = f"https://t.me/v00dooBot?start=ref_{user.id}"
    await update.message.reply_html(
        "👥 <b>Запроси друга — отримай 50 XP!</b>\n\n"
        "Поділись цим посиланням:\n"
        f"<code>{link}</code>\n\n"
        "Коли друг пройде перший урок — тобі +50 XP автоматично! 🎁",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📤 Поділитись",
                                 url=f"https://t.me/share/url?url={link}&text=Вчи+англійську+з+Voodoo!"),
        ]]),
    )


async def cmd_play(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🎮 Відкрий Voodoo Mini App:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🪄 Грати", web_app=WebAppInfo(url=MINIAPP_URL)),
        ]]),
    )


async def cmd_podcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Send user a personalized podcast based on their learned words."""
    user = update.effective_user
    msg  = await update.message.reply_text(
        "🎙 Генерую твій персональний подкаст...\n"
        "Це займе ~30 секунд ⏳"
    )
    try:
        from agents.podcast_agent import generate_and_send_personal
        ok = await generate_and_send_personal(user.id)
        if ok:
            await msg.delete()
        else:
            await msg.edit_text("❌ Не вдалось створити подкаст. Спробуй пізніше.")
    except Exception as e:
        log.error("cmd_podcast error: %s", e)
        await msg.edit_text("❌ Технічна помилка. Спробуй ще раз.")


async def cmd_leaderboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    stats = await db.get_stats()
    top10 = stats.get("top10", [])
    medals = ["🥇","🥈","🥉"] + ["4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    lines = ["🏆 <b>ТОП-10 Voodoo</b>\n"]
    for i, u in enumerate(top10[:10]):
        lines.append(f"{medals[i]} {u.get('first_name','?')} — {u.get('xp',0)} XP 🔥{u.get('streak',0)}д")
    await update.message.reply_html(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🎮 Повний рейтинг",
                                 web_app=WebAppInfo(url=MINIAPP_URL)),
        ]]),
    )


async def cmd_curr(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current week's 3 words from the 9-month curriculum."""
    try:
        from content_plan_9months import CURRICULUM
        now = datetime.now()
        # Match by month + week-of-month
        month = now.month
        week  = (now.day - 1) // 7 + 1
        plan  = next(
            (p for p in CURRICULUM if p["month"] == month and p["week"] == week),
            None,
        )
        if not plan:
            # Fall back to first available plan for this month
            plan = next((p for p in CURRICULUM if p["month"] == month), None)
        if not plan:
            await update.message.reply_text("📅 Розклад на цей місяць ще не додано. Ось слово дня:")
            await cmd_word(update, ctx)
            return

        # Show today's 3 words (day-of-week index 0-4)
        day_idx = min(now.weekday(), 4)  # Mon-Fri
        words   = plan["words"][day_idx * 3 : day_idx * 3 + 3]
        if not words:
            words = plan["words"][:3]

        lines = [
            f"📅 <b>Тиждень {plan['week']} — {plan['theme']}</b>\n",
            f"📐 Граматика: <i>{plan['grammar']}</i>\n",
        ]
        for w in words:
            lines.append(f"• <b>{w['en']}</b> — {w['ua']}")
            lines.append(f"  💬 <i>{w['example']}</i>\n")

        lines.append(f"🗣 Ідіома: <b>{plan['idiom']}</b>")
        lines.append(f"    <i>{plan['idiom_meaning']}</i>")

        await update.message.reply_html(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🎮 Практикувати в App",
                                     web_app=WebAppInfo(url=MINIAPP_URL)),
            ]]),
        )
    except Exception as e:
        log.error("cmd_curr: %s", e)
        await cmd_word(update, ctx)


async def cmd_subscribe(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Telegram Stars payment — Premium 30 days."""
    user = update.effective_user
    u = await db.get_user(user.id)

    if u.get("is_premium"):
        exp = u.get("premium_expires", "")
        await update.message.reply_html(
            f"💎 <b>Voodoo Premium вже активний!</b>\n\nДійсний до: <b>{exp}</b>\n\n"
            "Продовжити після закінчення:\n",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("💎 Продовжити Premium", callback_data="buy_premium"),
            ]]),
        )
        return

    await ctx.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title="💎 Voodoo Premium — 30 днів",
        description=(
            "✅ 2× XP за кожен урок\n"
            "✅ Преміум персонажі (Vex, Seraph)\n"
            "✅ 🏆 Значок у Leaderboard\n"
            "✅ Ексклюзивний контент"
        ),
        payload="premium_30",
        currency="XTR",
        prices=[LabeledPrice("Voodoo Premium 30 дн.", 75)],
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("💎 Оплатити 75 ⭐", pay=True),
        ]]),
    )


async def cmd_freeze(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Telegram Stars payment — Streak Freeze."""
    user = update.effective_user
    u = await db.get_user(user.id)
    current = u.get("streak_freeze", 0)

    await ctx.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title="❄️ Streak Freeze",
        description=(
            f"Захищає твою серію на 1 пропущений день.\n"
            f"Зараз у тебе: {current} заморожень\n\n"
            f"🔥 Серія: {u.get('streak', 0)} дн. — не втрать її!"
        ),
        payload="streak_freeze_1",
        currency="XTR",
        prices=[LabeledPrice("Streak Freeze ×1", 15)],
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❄️ Купити 15 ⭐", pay=True),
        ]]),
    )


async def pre_checkout(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Accept all pre-checkout queries."""
    await update.pre_checkout_query.answer(ok=True)


async def successful_payment(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle successful Stars payment."""
    user    = update.effective_user
    payment = update.message.successful_payment
    payload = payment.invoice_payload
    stars   = payment.total_amount

    u = await db.get_user(user.id)
    new_stars = u.get("stars_spent", 0) + stars

    if payload == "premium_30":
        expires = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        await db.update_user(
            user.id,
            is_premium=1,
            premium_expires=expires,
            stars_spent=new_stars,
        )
        await update.message.reply_html(
            "🎉 <b>Voodoo Premium активовано!</b>\n\n"
            f"✅ 2× XP за уроки — починаючи зараз!\n"
            f"✅ Розблоковані преміум персонажі\n"
            f"✅ Дійсний до: <b>{expires}</b>\n\n"
            "Відкрий App — обери нового персонажа 👇",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🎮 Відкрити App", web_app=WebAppInfo(url=MINIAPP_URL)),
            ]]),
        )
        log.info("Premium activated for user %d (75 Stars)", user.id)

    elif payload == "streak_freeze_1":
        new_freeze = u.get("streak_freeze", 0) + 1
        await db.update_user(user.id, streak_freeze=new_freeze, stars_spent=new_stars)
        await update.message.reply_html(
            f"❄️ <b>Streak Freeze додано!</b>\n\n"
            f"У тебе тепер <b>{new_freeze}</b> заморожень серії.\n"
            f"Використається автоматично якщо пропустиш день.",
        )
        log.info("Streak freeze +1 for user %d", user.id)


async def cb_generic(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data  = query.data

    if data == "lesson":
        await cmd_word(update, ctx)
    elif data == "leaderboard":
        await cmd_leaderboard(update, ctx)
    elif data == "profile":
        user = update.effective_user
        if user:
            await cmd_profile(update, ctx)
    elif data == "word_of_day":
        await cmd_word(update, ctx)
    elif data == "next_word":
        await cmd_word(update, ctx)
    elif data.startswith("know_"):
        user = update.effective_user
        if user:
            u = await db.get_user(user.id)
            await db.update_user(user.id, xp=u.get("xp",0)+5, total_words=u.get("total_words",0)+1)
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text("✅ Записано! +5 XP")
    elif data.startswith("pronounce_"):
        await query.message.reply_text(
            "🔊 Вимова доступна у @VoodooSpeakBot або в Mini App!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔊 VoodooSpeakBot", url="https://t.me/VoodooSpeakBot"),
            ]]),
        )
    elif data == "buy_premium":
        await cmd_subscribe(update, ctx)


# ── Setup commands ────────────────────────────────────────────────────────────

async def post_init(app: Application) -> None:
    await app.bot.set_my_commands([
        BotCommand("start",       "🪄 Почати / Головне меню"),
        BotCommand("word",        "📖 Слово дня"),
        BotCommand("quiz",        "❓ Швидкий квіз"),
        BotCommand("lessons",     "📚 Урок дня"),
        BotCommand("stats",       "📊 Моя статистика"),
        BotCommand("profile",     "👤 Профіль"),
        BotCommand("leaderboard", "🏆 Рейтинг"),
        BotCommand("play",        "🎮 Відкрити Mini App"),
        BotCommand("curr",        "📅 Слова поточного тижня"),
        BotCommand("invite",      "👥 Запросити друга (+50 XP)"),
        BotCommand("freeze",      "❄️ Заморожувач серії (15 ⭐)"),
        BotCommand("subscribe",   "💎 Voodoo Premium (75 ⭐)"),
        BotCommand("podcast",     "🎙 Персональний подкаст"),
        BotCommand("help",        "❓ Допомога"),
    ])
    db.init_db()
    log.info("VoodooBot ready")


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    app = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start",       cmd_start))
    app.add_handler(CommandHandler("help",        cmd_help))
    app.add_handler(CommandHandler("word",        cmd_word))
    app.add_handler(CommandHandler("quiz",        cmd_quiz))
    app.add_handler(CommandHandler("stats",       cmd_stats))
    app.add_handler(CommandHandler("profile",     cmd_profile))
    app.add_handler(CommandHandler("leaderboard", cmd_leaderboard))
    app.add_handler(CommandHandler("play",        cmd_play))
    app.add_handler(CommandHandler("lessons",     cmd_play))
    app.add_handler(CommandHandler("invite",      cmd_invite))
    app.add_handler(CommandHandler("podcast",     cmd_podcast))
    app.add_handler(CommandHandler("curr",        cmd_curr))
    app.add_handler(CommandHandler("subscribe",   cmd_subscribe))
    app.add_handler(CommandHandler("freeze",      cmd_freeze))
    app.add_handler(PreCheckoutQueryHandler(pre_checkout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))

    app.add_handler(CallbackQueryHandler(cb_level,   pattern=r"^level_"))
    app.add_handler(CallbackQueryHandler(cb_quiz,    pattern=r"^quiz_"))
    app.add_handler(CallbackQueryHandler(cb_generic))

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    log.info("VoodooBot polling (admin_id=%d)", ADMIN_ID)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
