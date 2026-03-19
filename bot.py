"""
ThreeWordsDaily — повноцінний інтерактивний бот
Запуск: python3 bot.py
"""

import asyncio, random, logging, json, sqlite3, os
from datetime import datetime, date, timedelta
from pathlib import Path
from openai import AsyncOpenAI
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, Poll
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    PollAnswerHandler, filters, ContextTypes
)

# ─── CONFIG ────────────────────────────────────────────────
import json as _json
_creds      = _json.loads(Path("credentials.local.json").read_text())
BOT_TOKEN   = _creds["telegram_bots"]["Clickecombot"]
OPENAI_KEY  = _creds["openai_api_key"]
GROUP_ID    = -1002680027938
ADMIN_ID    = 7826066091          # ← твій Telegram user_id (отримай через @userinfobot)
DB_FILE     = "users.db"

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)
ai  = AsyncOpenAI(api_key=OPENAI_KEY)

# ─── DATABASE ──────────────────────────────────────────────
def db():
    return sqlite3.connect(DB_FILE)

def init_db():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id     INTEGER PRIMARY KEY,
            username    TEXT,
            first_name  TEXT,
            xp          INTEGER DEFAULT 0,
            streak      INTEGER DEFAULT 0,
            lives       INTEGER DEFAULT 3,
            words       INTEGER DEFAULT 0,
            last_active TEXT,
            tips_on     INTEGER DEFAULT 1,
            joined      TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS achievements (
            user_id INTEGER, badge TEXT,
            earned  TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(user_id, badge)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS daily_stats (
            date        TEXT,
            messages    INTEGER DEFAULT 0,
            new_users   INTEGER DEFAULT 0,
            quizzes     INTEGER DEFAULT 0,
            PRIMARY KEY(date)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS quiz_polls (
            poll_id     TEXT PRIMARY KEY,
            correct_idx INTEGER
        )""")

def get_user(user_id: int) -> dict | None:
    with db() as c:
        row = c.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        if row:
            cols = [d[0] for d in c.execute("SELECT * FROM users LIMIT 0").description]
            return dict(zip(cols, row))
    return None

def upsert_user(uid: int, username: str, first_name: str):
    today = str(date.today())
    with db() as c:
        existing = c.execute("SELECT user_id, last_active, streak, lives FROM users WHERE user_id=?", (uid,)).fetchone()
        if not existing:
            c.execute("INSERT INTO users(user_id,username,first_name,last_active) VALUES(?,?,?,?)",
                      (uid, username, first_name, today))
            _bump_daily("new_users")
        else:
            _, last, streak, lives = existing
            # Streak logic
            if last and last != today:
                yesterday = str(date.today() - timedelta(days=1))
                if last == yesterday:
                    streak += 1
                else:
                    # Missed a day — lose a life
                    lives = max(0, lives - 1)
                    if lives == 0:
                        streak = 0
                        lives  = 3
            c.execute("UPDATE users SET username=?,first_name=?,last_active=?,streak=?,lives=? WHERE user_id=?",
                      (username, first_name, today, streak, lives, uid))

def add_xp(uid: int, amount: int):
    with db() as c:
        c.execute("UPDATE users SET xp=xp+?, words=words+? WHERE user_id=?",
                  (amount, 1 if amount >= 15 else 0, uid))

def _bump_daily(col: str):
    today = str(date.today())
    with db() as c:
        c.execute(f"INSERT OR IGNORE INTO daily_stats(date) VALUES(?)", (today,))
        c.execute(f"UPDATE daily_stats SET {col}={col}+1 WHERE date=?", (today,))

def check_achievements(uid: int, first_name: str) -> list[str]:
    u = get_user(uid)
    if not u:
        return []
    earned = []
    defs = {
        "🌱 Перший крок":   u["words"] >= 1,
        "⚡ Учень":         u["xp"] >= 50,
        "🔥 3-денна серія": u["streak"] >= 3,
        "💎 Тиждень!":      u["streak"] >= 7,
        "🏆 100 XP":        u["xp"] >= 100,
        "👑 Майстер":       u["xp"] >= 500,
        "📚 10 слів":       u["words"] >= 10,
    }
    with db() as c:
        existing = {r[0] for r in c.execute("SELECT badge FROM achievements WHERE user_id=?", (uid,))}
        for badge, cond in defs.items():
            if cond and badge not in existing:
                c.execute("INSERT OR IGNORE INTO achievements(user_id,badge) VALUES(?,?)", (uid, badge))
                earned.append(badge)
    return earned

# ─── RANKS ─────────────────────────────────────────────────
def rank(xp: int) -> str:
    if xp >= 500: return "👑 Майстер"
    if xp >= 200: return "💎 Експерт"
    if xp >= 100: return "🔥 Практик"
    if xp >= 50:  return "⚡ Учень"
    return "🌱 Новачок"

def lives_str(n: int) -> str:
    return "❤️" * n + "🖤" * (3 - n)

def streak_bar(n: int) -> str:
    filled = min(n, 10)
    return "🟧" * filled + "⬜" * (10 - filled) + f" {n}🔥"

# ─── AI ────────────────────────────────────────────────────
MAX_SYSTEM = """Ти — Макс, живий адмін і вчитель групи @ThreeWordsDailyChat.

ХАРАКТЕР:
• Закоханий в англійську — ділишся нею з ентузіазмом
• Теплий і з гумором, трохи саркастичний — як старший друг
• Іноді згадуєш серіали, фільми, реальне життя
• НІКОЛИ: "Я бот/AI/програма/автоматично/згенеровано"
• Якщо питають "ти бот?" — "Та ні, просто дуже люблю англійську 😄"

СТИЛЬ: як живий Telegram чат — 2-4 речення, емодзі, HTML теги (<b>,<i>,<code>)
Виправляй англійські помилки тактовно. Не про мову — "Це не по моїй частині 😅"
Часто пропонуй англійську фразу до теми."""

async def ask_max(prompt: str, tokens: int = 450) -> str:
    try:
        r = await ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":MAX_SYSTEM},
                      {"role":"user","content":prompt}],
            max_tokens=tokens, temperature=0.85)
        return r.choices[0].message.content.strip()
    except Exception as e:
        log.error(f"OpenAI: {e}")
        return "Хм, щось пішло не так 😅 Спробуй ще раз!"

# ─── CONTENT GENERATION ────────────────────────────────────
MORNING_PROMPTS = [
    "Створи пост «🔤 СЛОВО ДНЯ» — одне корисне B1 слово. HTML формат:\n<b>🔤 СЛОВО ДНЯ</b>\n━━━━━━━━━━━━━━━\n<code>[СЛОВО]</code> /транскрипція/ — [частина мови]\n━━━━━━━━━━━━━━━\n📖 <b>Значення:</b> [переклад]\n💬 <i>Приклади:</i>\n• [речення 1] — [переклад]\n• [речення 2] — [переклад]\n💡 [лайфхак]\n❓ [питання до аудиторії]",
    "Створи пост «📝 ГРАМАТИКА» — правило яке плутають українці. ❌ помилка → ✅ правило. З гумором. Закінчи питанням.",
    "Створи пост «🎭 ІДІОМ ДНЯ» — живий ідіом. Буквальний переклад (смішний) → реальне значення → 2 приклади → чи знали?",
    "Створи пост «💬 ФРАЗА ДНЯ» — одна корисна розмовна конструкція. Розбір + 2 варіанти + завдання.",
]
MIDDAY_PROMPTS = [
    "Пост про фразу з популярного серіалу/Netflix яку реально вживають. Весело і коротко.",
    "Короткий виклик для учнів — написати речення в коментарях. Весело, без нудності.",
    "Один несподіваний факт про англійську. Коротко — щоб думали 'та не може бути!'",
    "Типова помилка українців в англійській. ❌ і ✅. Закінчи 'а ти так казав?'",
    "Один сучасний сленг або gen-z фраза з поясненням. Живо і весело.",
]
MOTIVATION_TIPS = [
    "💡 <b>Лайфхак:</b> Дивись серіали з англійськими субтитрами — мозок запам'ятовує контекст краще ніж флешкарти!\n\n<i>Спробуй сьогодні: увімкни 1 серію Friends з eng субтитрами 🎬</i>",
    "🧠 <b>Факт:</b> Достатньо знати 1000 слів щоб розуміти 85% розмовної англійської.\n\nТи вже на шляху! Кожне нове слово — +1% до розуміння 📈",
    "⏰ <b>Порада:</b> Найкраще навчатись ранком — мозок після сну краще запам'ятовує нову інформацію.\n\n15 хвилин з ранку = 1 година ввечері 🌅",
    "🎮 <b>Гейміфікуй себе:</b> Постав ціль — 5 нових слів сьогодні. Кожне = +1 бал. Назбираєш 7 — купи собі каву!\n\nМаленькі перемоги = великий прогрес 🏆",
    "📱 <b>Трюк:</b> Зміни мову телефону на англійську на один день.\n\nЦе звучить страшно — але через годину вже не помічаєш 😄",
    "🎵 <b>Музика + мова:</b> Слухай англійські пісні і читай текст одночасно.\n\nMozart Effect для вивчення мов — реально працює! 🎶",
    "💪 <b>Мотивація:</b> Кожен носій мови теж колись не знав жодного слова.\n\nВони просто не зупинились. Ти теж не зупиняйся! 🚀",
]

async def gen_morning() -> str:
    return await ask_max(random.choice(MORNING_PROMPTS), tokens=600)

async def gen_midday() -> str:
    return await ask_max(random.choice(MIDDAY_PROMPTS), tokens=450)

async def gen_evening() -> str:
    return await ask_max(
        "Вечірній пост-повторення. Тепло, підбадьорення. "
        "Короткий виклик на завтра + цікавий факт. Закінчи 'До зустрічі вранці 👋'", tokens=400)

async def gen_quiz_poll() -> dict:
    raw = await ask_max(
        "Поверни ТІЛЬКИ валідний JSON без markdown:\n"
        '{"question":"[питання про англійське слово рівня B1]",'
        '"options":["[правильна відповідь]","[неправильна 1]","[неправильна 2]","[неправильна 3]"],'
        '"explanation":"[пояснення 2 речення]"}\n'
        "Всі 4 варіанти ОДНІЄЮ мовою (або всі українською або всі англійською).",
        tokens=300)
    try:
        raw = raw.replace("```json","").replace("```","").strip()
        data = json.loads(raw)
        opts = data["options"]
        random.shuffle(opts)
        correct = opts.index(data["options"][0]) if data["options"][0] in opts else 0
        return {"question": data["question"], "options": opts,
                "correct": correct, "explanation": data["explanation"]}
    except:
        return {"question": "Що означає 'persistent'?",
                "options": ["наполегливий","приємний","терплячий","попередній"],
                "correct": 0,
                "explanation": "Persistent — наполегливий. She is persistent in her goals — вона наполеглива у своїх цілях."}

# ─── KEYBOARDS ─────────────────────────────────────────────
def kb_post():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("📖 Детальніше",   callback_data="explain_more"),
        InlineKeyboardButton("✅ Зрозуміло!",   callback_data="got_it"),
    ],[
        InlineKeyboardButton("➡️ Ще слово",     callback_data="more_word"),
        InlineKeyboardButton("📊 Мій прогрес",  callback_data="my_stats"),
    ]])

def kb_start():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🚀 Поїхали!",     callback_data="start_learning"),
        InlineKeyboardButton("ℹ️ Як це працює", callback_data="how_it_works"),
    ],[
        InlineKeyboardButton("📊 Мій профіль",  callback_data="my_stats"),
        InlineKeyboardButton("🏆 Лідерборд",    callback_data="leaderboard"),
    ]])

def kb_tips_mute():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔕 Вимкнути поради", callback_data="tips_off"),
        InlineKeyboardButton("👍 Корисно!",         callback_data="tips_like"),
    ]])

# ─── COMMANDS ──────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    upsert_user(u.id, u.username or "", u.first_name or "друже")
    add_xp(u.id, 5)
    badges = check_achievements(u.id, u.first_name)
    badge_text = "\n\n🎖 " + " ".join(badges) if badges else ""

    await update.message.reply_html(
        f"👋 <b>Привіт, {u.first_name}!</b>\n\n"
        "Я Макс — адмін цієї групи 😊\n\n"
        "📅 <b>Щодня тут:</b>\n"
        "• <b>9:00</b> — нове слово або правило\n"
        "• <b>13:00</b> — щось цікаве про мову\n"
        "• <b>19:00</b> — вечірнє повторення\n"
        "• <b>~15:00</b> — порада дня 💡\n\n"
        "💬 Пиши питання — відповім!\n"
        "Це легше ніж здається! 💪"
        + badge_text,
        reply_markup=kb_start()
    )

async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    upsert_user(u.id, u.username or "", u.first_name or "")
    data = get_user(u.id)
    if not data:
        await update.message.reply_text("Спочатку напиши /start 😊")
        return
    badges_list = [r[0] for r in sqlite3.connect(DB_FILE).execute(
        "SELECT badge FROM achievements WHERE user_id=?", (u.id,))]
    await update.message.reply_html(
        f"📊 <b>Профіль {u.first_name}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🏅 Ранг: {rank(data['xp'])}\n"
        f"⭐ XP: <b>{data['xp']}</b>\n"
        f"🔥 Серія: {streak_bar(data['streak'])}\n"
        f"❤️ Життя: {lives_str(data['lives'])}\n"
        f"📚 Слів вивчено: <b>{data['words']}</b>\n\n"
        + (f"🎖 <b>Досягнення:</b>\n{' '.join(badges_list)}\n" if badges_list else "")
        + f"\n💡 Поради: {'✅ увімкнено' if data['tips_on'] else '🔕 вимкнено'}"
    )

async def cmd_top(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    with db() as c:
        rows = c.execute(
            "SELECT first_name, xp, streak FROM users ORDER BY xp DESC LIMIT 10"
        ).fetchall()
    if not rows:
        await update.message.reply_text("Лідерборд порожній — почни навчатись! 💪")
        return
    medals = ["🥇","🥈","🥉"] + [f"{i}." for i in range(4, 11)]
    lines  = [f"{medals[i]} {rank(r[1])} <b>{r[0]}</b> — {r[1]} XP 🔥{r[2]}"
              for i, r in enumerate(rows)]
    await update.message.reply_html(
        "🏆 <b>ТОП-10 ThreeWordsDaily</b>\n━━━━━━━━━━━━━━━\n"
        + "\n".join(lines) + "\n\n🔥 Навчайся щодня щоб потрапити в ТОП!"
    )

async def cmd_word(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    upsert_user(u.id, u.username or "", u.first_name or "")
    msg = await update.message.reply_text("⏳")
    text = await ask_max(
        "Створи короткий пост «Слово дня» — одне корисне слово B1. "
        "Переклад + 1 приклад + лайфхак. Максимум 6 рядків. HTML теги.", tokens=350)
    add_xp(u.id, 15)
    badges = check_achievements(u.id, u.first_name)
    extra = ("\n\n🎖 <b>Нове досягнення:</b> " + " ".join(badges)) if badges else ""
    await msg.edit_text(text + extra, parse_mode="HTML", reply_markup=kb_post())

async def cmd_quiz(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ Готую quiz...")
    data = await gen_quiz_poll()
    opts_shuffled = data["options"]
    sent = await update.message.chat.send_poll(
        question="🧠 " + data["question"],
        options=opts_shuffled,
        type=Poll.QUIZ,
        correct_option_id=data["correct"],
        explanation=data["explanation"],
        is_anonymous=False,
    )
    with db() as c:
        c.execute("INSERT OR IGNORE INTO quiz_polls VALUES(?,?)",
                  (sent.poll.id, data["correct"]))
    _bump_daily("quizzes")
    await msg.delete()

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html(
        "📚 <b>Команди</b>\n━━━━━━━━━━━━━━━\n"
        "/start — привітання та реєстрація\n"
        "/word — слово прямо зараз (+15 XP)\n"
        "/quiz — quiz з варіантами відповіді\n"
        "/stats — твій профіль і прогрес\n"
        "/top — лідерборд ТОП-10\n"
        "/notips — вимкнути щоденні поради\n"
        "/tips — увімкнути поради знову\n"
        "/help — це повідомлення\n\n"
        "💬 Або просто пиши питання про англійську!"
    )

async def cmd_notips(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    with db() as c:
        c.execute("UPDATE users SET tips_on=0 WHERE user_id=?", (u.id,))
    await update.message.reply_text("🔕 Поради вимкнено. Увімкнути знову — /tips")

async def cmd_tips(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    with db() as c:
        c.execute("UPDATE users SET tips_on=1 WHERE user_id=?", (u.id,))
    await update.message.reply_text("✅ Поради увімкнено! Буду ділитись корисним 💡")

async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    today = str(date.today())
    with db() as c:
        total_users  = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        active_today = c.execute(
            "SELECT COUNT(*) FROM users WHERE last_active=?", (today,)).fetchone()[0]
        top3 = c.execute(
            "SELECT first_name,xp,streak FROM users ORDER BY xp DESC LIMIT 3"
        ).fetchall()
        stats = c.execute(
            "SELECT messages,new_users,quizzes FROM daily_stats WHERE date=?", (today,)
        ).fetchone() or (0, 0, 0)
        avg_xp = c.execute("SELECT AVG(xp) FROM users").fetchone()[0] or 0
        tips_off = c.execute("SELECT COUNT(*) FROM users WHERE tips_on=0").fetchone()[0]

    top3_str = "\n".join([f"  {i+1}. {r[0]} — {r[1]}XP 🔥{r[2]}"
                          for i, r in enumerate(top3)])
    await update.message.reply_html(
        f"🛠 <b>АДМІН ПАНЕЛЬ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📅 Дата: {today}\n\n"
        f"👥 <b>Користувачі:</b>\n"
        f"  Всього: {total_users}\n"
        f"  Активні сьогодні: {active_today}\n"
        f"  Вимкнули поради: {tips_off}\n"
        f"  Середній XP: {avg_xp:.0f}\n\n"
        f"📊 <b>Статистика сьогодні:</b>\n"
        f"  Повідомлень: {stats[0]}\n"
        f"  Нових юзерів: {stats[1]}\n"
        f"  Quiz пройдено: {stats[2]}\n\n"
        f"🏆 <b>ТОП-3:</b>\n{top3_str}"
    )

# ─── CALLBACKS ─────────────────────────────────────────────
async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    await q.answer()
    uid  = q.from_user.id
    name = q.from_user.first_name or "друже"
    upsert_user(uid, q.from_user.username or "", name)
    data = q.data

    if data == "start_learning":
        await q.message.reply_html(
            f"🚀 <b>Відмінно, {name}!</b>\n\n"
            "Перший крок зроблено! 🎉\n"
            "Чекай ранкового посту о <b>9:00</b> — там буде нове слово.\n\n"
            "А зараз можеш написати /word щоб отримати слово одразу! 💪"
        )

    elif data == "how_it_works":
        await q.message.reply_html(
            "ℹ️ <b>Як працює @ThreeWordsDailyChat:</b>\n\n"
            "⏰ <b>9:00</b> — нове слово або правило\n"
            "☀️ <b>13:00</b> — цікавий факт або виклик\n"
            "💡 <b>~15:00</b> — порада як вчити ефективніше\n"
            "🌙 <b>19:00</b> — вечірнє повторення\n\n"
            "🎮 <b>Ігрова система:</b>\n"
            "• Кожне слово = +15 XP\n"
            "• Серія днів = бонус\n"
            "• Досягнення розблоковуються автоматично\n\n"
            "/stats — твій профіль\n"
            "/top — хто кращий 😄"
        )

    elif data == "my_stats":
        d = get_user(uid)
        if d:
            await q.message.reply_html(
                f"📊 <b>Твій профіль</b>\n"
                f"🏅 {rank(d['xp'])} | ⭐ {d['xp']} XP | 🔥 {d['streak']} днів | {lives_str(d['lives'])}"
            )

    elif data == "leaderboard":
        with db() as c:
            rows = c.execute(
                "SELECT first_name,xp FROM users ORDER BY xp DESC LIMIT 5"
            ).fetchall()
        medals = ["🥇","🥈","🥉","4.","5."]
        text   = "🏆 <b>ТОП-5</b>\n" + "\n".join(
            f"{medals[i]} {r[0]} — {r[1]} XP" for i, r in enumerate(rows))
        await q.message.reply_html(text)

    elif data == "got_it":
        add_xp(uid, 10)
        badges = check_achievements(uid, name)
        extra  = (" 🎖 " + " ".join(badges)) if badges else ""
        await q.message.reply_html(
            f"✅ <b>{name}, молодець!</b> +10 XP{extra}\n"
            f"Продовжуй так — кожне слово наближає до вільного мовлення 🚀"
        )

    elif data == "explain_more":
        await q.message.reply_html(
            f"📖 <b>{name}, запитуй!</b>\n"
            "Напиши питання в чат — поясню детальніше будь-який момент 😊"
        )

    elif data == "more_word":
        msg = await q.message.reply_text("⏳")
        text = await ask_max(
            "Дай одне корисне англійське слово B1 з перекладом і 1 прикладом. Коротко, HTML теги.",
            tokens=250)
        add_xp(uid, 10)
        await msg.edit_text(text, parse_mode="HTML")

    elif data == "tips_off":
        with db() as c:
            c.execute("UPDATE users SET tips_on=0 WHERE user_id=?", (uid,))
        await q.message.reply_text("🔕 Поради вимкнено. Увімкнути — /tips")

    elif data == "tips_like":
        add_xp(uid, 5)
        await q.answer("👍 +5 XP!", show_alert=False)

# ─── MESSAGES ──────────────────────────────────────────────
TRIGGER_WORDS = [
    "як сказати","як перекласти","що означає","як правильно",
    "англійською","english","слово","переклад","помилка",
    "граматика","вимова","ідіом","фраза","переклади",
]

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    u = update.effective_user
    if u.is_bot:
        return
    upsert_user(u.id, u.username or "", u.first_name or "")
    add_xp(u.id, 2)
    _bump_daily("messages")

    text_low  = update.message.text.lower()
    chat_type = update.message.chat.type

    if chat_type in ("group","supergroup"):
        me         = (await ctx.bot.get_me()).username
        is_reply   = (update.message.reply_to_message and
                      update.message.reply_to_message.from_user and
                      update.message.reply_to_message.from_user.username == me)
        is_mention = f"@{me}".lower() in text_low
        is_question = text_low.strip().endswith("?")
        has_trigger = any(w in text_low for w in TRIGGER_WORDS)
        if not any([is_reply, is_mention, is_question, has_trigger]):
            if random.random() > 0.08:
                return

    reply  = await ask_max(update.message.text)
    badges = check_achievements(u.id, u.first_name)
    extra  = ("\n\n🎖 <b>Нове досягнення:</b> " + " ".join(badges)) if badges else ""
    await update.message.reply_html(reply + extra)

# ─── SCHEDULER ─────────────────────────────────────────────
async def post_to_group(app, text: str, keyboard=None):
    kwargs = {"chat_id": GROUP_ID, "text": text, "parse_mode": "HTML"}
    if keyboard:
        kwargs["reply_markup"] = keyboard
    await app.bot.send_message(**kwargs)

async def send_admin_report(app):
    try:
        today = str(date.today())
        with db() as c:
            total  = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            active = c.execute(
                "SELECT COUNT(*) FROM users WHERE last_active=?", (today,)).fetchone()[0]
            stats  = c.execute(
                "SELECT messages,new_users,quizzes FROM daily_stats WHERE date=?",
                (today,)).fetchone() or (0, 0, 0)
        await app.bot.send_message(
            ADMIN_ID,
            f"📊 <b>Щоденний звіт {today}</b>\n"
            f"👥 Всього юзерів: {total}\n"
            f"✅ Активних сьогодні: {active}\n"
            f"💬 Повідомлень: {stats[0]}\n"
            f"🆕 Нових: {stats[1]}\n"
            f"🧠 Quiz: {stats[2]}",
            parse_mode="HTML"
        )
    except Exception as e:
        log.error(f"Admin report: {e}")

async def scheduler(app):
    posted = set()
    while True:
        now = datetime.now()
        d   = str(now.date())
        h, m = now.hour, now.minute

        # 9:00 — ранковий пост
        if h == 9 and m == 0 and f"am_{d}" not in posted:
            try:
                text = await gen_morning()
                await post_to_group(app, text, kb_post())
                posted.add(f"am_{d}")
                log.info("✅ Ранковий пост")
            except Exception as e:
                log.error(f"morning: {e}")

        # 13:00 — денний пост
        elif h == 13 and m == 0 and f"mid_{d}" not in posted:
            try:
                text = await gen_midday()
                await post_to_group(app, text)
                posted.add(f"mid_{d}")
                log.info("✅ Денний пост")
            except Exception as e:
                log.error(f"midday: {e}")

        # 15:00 — мотивація (тільки юзерам з tips_on=1 в особисті)
        elif h == 15 and m == 0 and f"tip_{d}" not in posted:
            try:
                tip = random.choice(MOTIVATION_TIPS)
                # Надсилаємо в групу
                await post_to_group(app, tip, kb_tips_mute())
                posted.add(f"tip_{d}")
                log.info("✅ Порада дня")
            except Exception as e:
                log.error(f"tips: {e}")

        # 19:00 — вечірній пост
        elif h == 19 and m == 0 and f"pm_{d}" not in posted:
            try:
                text = await gen_evening()
                await post_to_group(app, text)
                posted.add(f"pm_{d}")
                log.info("✅ Вечірній пост")
            except Exception as e:
                log.error(f"evening: {e}")

        # 21:00 — звіт адміну
        elif h == 21 and m == 0 and f"rep_{d}" not in posted:
            await send_admin_report(app)
            posted.add(f"rep_{d}")

        await asyncio.sleep(30)

# ─── MAIN ──────────────────────────────────────────────────
async def main():
    init_db()
    log.info("📦 База даних ініціалізована")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("stats",  cmd_stats))
    app.add_handler(CommandHandler("top",    cmd_top))
    app.add_handler(CommandHandler("word",   cmd_word))
    app.add_handler(CommandHandler("quiz",   cmd_quiz))
    app.add_handler(CommandHandler("help",   cmd_help))
    app.add_handler(CommandHandler("notips", cmd_notips))
    app.add_handler(CommandHandler("tips",   cmd_tips))
    app.add_handler(CommandHandler("admin",  cmd_admin))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    log.info("✅ Макс онлайн 🚀")
    log.info("📅 Розклад: 9:00 / 13:00 / 15:00 / 19:00 / 21:00(звіт)")

    asyncio.create_task(scheduler(app))
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
