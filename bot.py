"""
ThreeWordsDaily — повноцінний інтерактивний бот
Запуск: python3 bot.py
"""

import asyncio, random, logging, json, sqlite3
from datetime import datetime, date, timedelta
from pathlib import Path
from openai import AsyncOpenAI
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Poll
from telegram.error import Forbidden
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

# ─── CONFIG ────────────────────────────────────────────────
_creds     = json.loads(Path("credentials.local.json").read_text())
BOT_TOKEN  = _creds["telegram_bots"]["Clickecombot"]
OPENAI_KEY = _creds["openai_api_key"]
GROUP_ID   = -1002680027938
ADMIN_ID   = 1371213874       # Dre3am
BOT_USER   = "Clickecombot"
DB_FILE    = "users.db"

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)
ai  = AsyncOpenAI(api_key=OPENAI_KEY)

# ─── DATABASE ──────────────────────────────────────────────
def db():
    c = sqlite3.connect(DB_FILE, timeout=30, check_same_thread=False)
    c.execute("PRAGMA journal_mode=WAL")
    return c

def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id    INTEGER PRIMARY KEY,
            username   TEXT, first_name TEXT,
            xp         INTEGER DEFAULT 0,
            streak     INTEGER DEFAULT 0,
            lives      INTEGER DEFAULT 3,
            words      INTEGER DEFAULT 0,
            last_active TEXT,
            tips_on    INTEGER DEFAULT 1,
            joined     TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS achievements (
            user_id INTEGER, badge TEXT,
            earned  TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(user_id, badge)
        );
        CREATE TABLE IF NOT EXISTS daily_stats (
            dt       TEXT PRIMARY KEY,
            messages INTEGER DEFAULT 0,
            new_u    INTEGER DEFAULT 0,
            quizzes  INTEGER DEFAULT 0
        );
        """)

def bump(col: str):
    today = str(date.today())
    with db() as c:
        c.execute("INSERT OR IGNORE INTO daily_stats(dt) VALUES(?)", (today,))
        c.execute(f"UPDATE daily_stats SET {col}={col}+1 WHERE dt=?", (today,))

def get_user(uid: int) -> dict | None:
    with db() as c:
        row = c.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
        if not row: return None
        cols = [d[0] for d in c.execute("SELECT * FROM users LIMIT 0").description]
        return dict(zip(cols, row))

def upsert_user(uid: int, username: str, first_name: str):
    today = str(date.today())
    with db() as c:
        ex = c.execute("SELECT last_active,streak,lives FROM users WHERE user_id=?", (uid,)).fetchone()
        if not ex:
            c.execute("INSERT INTO users(user_id,username,first_name,last_active) VALUES(?,?,?,?)",
                      (uid, username, first_name, today))
            bump("new_u")
        else:
            last, streak, lives = ex
            if last and last != today:
                yesterday = str(date.today() - timedelta(days=1))
                if last == yesterday:
                    streak += 1
                else:
                    lives = max(0, lives - 1)
                    if lives == 0:
                        streak, lives = 0, 3
            c.execute("UPDATE users SET username=?,first_name=?,last_active=?,streak=?,lives=? WHERE user_id=?",
                      (username, first_name, today, streak, lives, uid))

def add_xp(uid: int, xp: int, word: bool = False):
    with db() as c:
        c.execute("UPDATE users SET xp=xp+?,words=words+? WHERE user_id=?",
                  (xp, 1 if word else 0, uid))

def check_badges(uid: int) -> list[str]:
    u = get_user(uid)
    if not u: return []
    defs = {
        "🌱 Перший крок":   u["words"] >= 1,
        "⚡ Учень":          u["xp"]   >= 50,
        "🔥 3 дні поспіль": u["streak"] >= 3,
        "💎 Тиждень!":      u["streak"] >= 7,
        "🏆 100 XP":        u["xp"]   >= 100,
        "👑 Майстер":       u["xp"]   >= 500,
        "📚 10 слів":       u["words"] >= 10,
    }
    new = []
    with db() as c:
        have = {r[0] for r in c.execute("SELECT badge FROM achievements WHERE user_id=?", (uid,))}
        for badge, ok in defs.items():
            if ok and badge not in have:
                c.execute("INSERT OR IGNORE INTO achievements VALUES(?,?,CURRENT_TIMESTAMP)", (uid, badge))
                new.append(badge)
    return new

# ─── HELPERS ───────────────────────────────────────────────
def rank(xp):
    if xp >= 500: return "👑 Майстер"
    if xp >= 200: return "💎 Експерт"
    if xp >= 100: return "🔥 Практик"
    if xp >= 50:  return "⚡ Учень"
    return "🌱 Новачок"

def lives_str(n): return "❤️"*n + "🖤"*(3-n)
def sbar(n): return "🟧"*min(n,10) + "⬜"*(10-min(n,10)) + f" {n}🔥"

def is_group(update: Update) -> bool:
    return update.effective_chat.type in ("group","supergroup")

async def send_private(ctx: ContextTypes.DEFAULT_TYPE, uid: int, text: str, **kw):
    """Відправляє в приват. Повертає True якщо успішно."""
    try:
        await ctx.bot.send_message(uid, text, **kw)
        return True
    except Forbidden:
        return False

# ─── KEYBOARDS ─────────────────────────────────────────────
KB_GO_PRIVATE = InlineKeyboardMarkup([[
    InlineKeyboardButton("💬 Написати Максу особисто", url=f"https://t.me/{BOT_USER}?start=hi")
]])

def kb_start():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🚀 Поїхали!",      callback_data="start_ok"),
        InlineKeyboardButton("ℹ️ Як це працює",  callback_data="how_it_works"),
    ],[
        InlineKeyboardButton("📊 Мій профіль",   callback_data="my_stats"),
        InlineKeyboardButton("🏆 Лідерборд",     callback_data="leaderboard"),
    ]])

def kb_post():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("📖 Детальніше",    callback_data="explain_more"),
        InlineKeyboardButton("✅ Зрозуміло! +XP", callback_data="got_it"),
    ],[
        InlineKeyboardButton("➡️ Ще слово",      callback_data="more_word"),
    ]])

def kb_tips():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔕 Вимкнути поради", callback_data="tips_off"),
        InlineKeyboardButton("👍 Корисно!",         callback_data="tips_like"),
    ]])

# ─── AI ────────────────────────────────────────────────────
MAX_SYSTEM = """Ти — Макс, живий адмін і вчитель групи @ThreeWordsDailyChat.

ХАРАКТЕР:
• Закоханий в англійську, ділишся з ентузіазмом
• Теплий, з гумором, як старший друг
• НІКОЛИ: "Я бот/AI/програма/автоматично" — ти просто Макс
• Якщо питають "ти бот?" → "Та ні, просто дуже люблю англійську 😄"

СТИЛЬ: живий Telegram чат, 2-4 речення, емодзі, HTML: <b>,<i>,<code>
Виправляй англійські помилки тактовно. Не про мову → "Це не по моїй частині 😅"
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
        return "Щось пішло не так 😅 Спробуй ще раз!"

# ─── CONTENT ───────────────────────────────────────────────
MORNING = [
    "Пост «🔤 СЛОВО ДНЯ» — одне B1 слово. HTML:\n<b>🔤 СЛОВО ДНЯ</b>\n━━━━━━━━━━━━━━━\n<code>[СЛОВО]</code> /транскрипція/ — [частина мови]\n━━━━━━━━━━━━━━━\n📖 [переклад]\n💬 [2 приклади]\n💡 [лайфхак]\n❓ [питання]",
    "Пост «📝 ГРАМАТИКА» — правило яке плутають українці. ❌→✅. З гумором. Закінчи питанням.",
    "Пост «🎭 ІДІОМ ДНЯ» — живий ідіом. Буквальний переклад → реальне значення → 2 приклади → питання.",
    "Пост «💬 ФРАЗА ДНЯ» — одна корисна конструкція B1. Розбір + 2 варіанти + завдання.",
]
MIDDAY = [
    "Пост про фразу з популярного серіалу/Netflix яку реально вживають. Весело і коротко. Питання.",
    "Короткий виклик — написати речення в коментарях. Весело, без нудності.",
    "Один несподіваний факт про англійську. Щоб думали 'та не може бути!'",
    "Типова помилка українців: ❌ і ✅. Закінчи 'а ти так казав?'",
    "Один gen-z сленг або вірусна фраза. Що означає + чи є аналог по-українськи.",
]
TIPS = [
    "💡 <b>Лайфхак:</b> Дивись серіали з англійськими субтитрами — мозок запам'ятовує контекст краще ніж флешкарти!\n\n<i>Спробуй сьогодні: 1 серія Friends з eng субтитрами 🎬</i>",
    "🧠 <b>Факт:</b> 1000 слів = 85% розмовної англійської. Ти вже на шляху! Кожне нове слово +1% 📈",
    "⏰ <b>Порада:</b> Ранок — найкращий час для навчання. 15 хв зранку = 1 година ввечері 🌅",
    "🎮 <b>Гейміфікуй:</b> 5 нових слів сьогодні = кава собі у подарунок. Маленькі перемоги — великий прогрес 🏆",
    "📱 <b>Трюк:</b> Зміни мову телефону на англійську на один день. Через годину вже не помічаєш 😄",
    "🎵 <b>Музика:</b> Слухай англійські пісні і читай текст одночасно. Реально працює! 🎶",
    "💪 <b>Мотивація:</b> Кожен носій мови теж колись не знав жодного слова. Вони просто не зупинились 🚀",
]

async def gen(prompts) -> str:
    return await ask_max(random.choice(prompts), tokens=600)

async def gen_quiz() -> dict:
    raw = await ask_max(
        'Поверни ТІЛЬКИ JSON без markdown:\n'
        '{"question":"[питання про англійське слово B1]",'
        '"options":["[правильна]","[неправильна 1]","[неправильна 2]","[неправильна 3]"],'
        '"explanation":"[пояснення 2 речення]"}\n'
        "Всі 4 варіанти ОДНІЄЮ мовою.", tokens=300)
    try:
        data = json.loads(raw.replace("```json","").replace("```","").strip())
        opts = data["options"][:]
        correct_ans = opts[0]
        random.shuffle(opts)
        return {"question": data["question"], "options": opts,
                "correct": opts.index(correct_ans), "explanation": data["explanation"]}
    except:
        return {"question":"Що означає 'resilient'?",
                "options":["стійкий","розумний","швидкий","сильний"],
                "correct":0,"explanation":"Resilient — стійкий, витривалий."}

# ─── COMMANDS ──────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    upsert_user(u.id, u.username or "", u.first_name or "друже")
    add_xp(u.id, 5)

    # В ГРУПІ — коротко, redirect у приват
    if is_group(update):
        await update.message.reply_html(
            f"👋 {u.first_name}! Напиши мені в особисті — там поговоримо без зайвого шуму 😊",
            reply_markup=KB_GO_PRIVATE
        )
        return

    # В ПРИВАТІ — повноцінно
    badges = check_badges(u.id)
    extra  = ("\n\n🎖 <b>Перше досягнення:</b> " + " ".join(badges)) if badges else ""
    await update.message.reply_html(
        f"👋 <b>Привіт, {u.first_name}!</b>\n\n"
        "Я Макс — адмін @ThreeWordsDailyChat 😊\n\n"
        "📅 <b>Щодня в групі:</b>\n"
        "• <b>9:00</b> — нове слово або правило\n"
        "• <b>13:00</b> — щось цікаве\n"
        "• <b>15:00</b> — порада дня 💡\n"
        "• <b>19:00</b> — вечірнє повторення\n\n"
        "🎮 <b>Тут в особистих:</b>\n"
        "/word — слово зараз (+15 XP)\n"
        "/quiz — тест\n"
        "/stats — твій прогрес\n"
        "/top — хто кращий 😄\n\n"
        "Це легше ніж здається! 💪" + extra,
        reply_markup=kb_start()
    )

async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    upsert_user(u.id, u.username or "", u.first_name or "")
    d = get_user(u.id)
    if not d:
        await update.message.reply_text("Спочатку /start 😊"); return

    with db() as c:
        bl = [r[0] for r in c.execute("SELECT badge FROM achievements WHERE user_id=?", (u.id,))]

    text = (
        f"📊 <b>Профіль {u.first_name}</b>\n━━━━━━━━━━━━━━━\n"
        f"🏅 {rank(d['xp'])}\n"
        f"⭐ XP: <b>{d['xp']}</b>\n"
        f"🔥 Серія: {sbar(d['streak'])}\n"
        f"❤️ Життя: {lives_str(d['lives'])}\n"
        f"📚 Слів: <b>{d['words']}</b>\n"
        + (f"\n🎖 {' '.join(bl)}" if bl else "")
        + f"\n\n💡 Поради: {'✅' if d['tips_on'] else '🔕 /tips щоб увімкнути'}"
    )

    if is_group(update):
        ok = await send_private(ctx, u.id, text, parse_mode="HTML")
        reply = "📊 Відправив твій профіль в особисті 👉" if ok else text
        await update.message.reply_html(reply)
    else:
        await update.message.reply_html(text)

async def cmd_top(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    with db() as c:
        rows = c.execute("SELECT first_name,xp,streak FROM users ORDER BY xp DESC LIMIT 10").fetchall()
    medals = ["🥇","🥈","🥉"] + [f"{i}." for i in range(4,11)]
    lines  = [f"{medals[i]} {rank(r[1])} <b>{r[0]}</b> — {r[1]} XP 🔥{r[2]}" for i,r in enumerate(rows)]
    await update.message.reply_html(
        "🏆 <b>ТОП-10</b>\n━━━━━━━━━━━━━━━\n"
        + ("\n".join(lines) if lines else "Поки порожньо — почни навчатись! 💪")
        + "\n\n🔥 Навчайся щодня щоб потрапити в ТОП!"
    )

async def cmd_word(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    upsert_user(u.id, u.username or "", u.first_name or "")

    if is_group(update):
        await update.message.reply_html(
            "📚 Надішлю тобі слово в особисті! 👉",
            reply_markup=KB_GO_PRIVATE
        )
        msg = await ctx.bot.send_message(u.id, "⏳")
    else:
        msg = await update.message.reply_text("⏳")

    text   = await ask_max("Одне корисне B1 слово: переклад + 1 приклад + лайфхак. 6 рядків max. HTML теги.", 350)
    add_xp(u.id, 15, word=True)
    badges = check_badges(u.id)
    extra  = ("\n\n🎖 " + " ".join(badges)) if badges else ""
    await msg.edit_text(text + extra + "\n\n+15 XP", parse_mode="HTML", reply_markup=kb_post())

async def cmd_quiz(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    upsert_user(u.id, u.username or "", u.first_name or "")

    if is_group(update):
        data = await gen_quiz()
        sent = await update.message.chat.send_poll(
            question="🧠 " + data["question"],
            options=data["options"], type=Poll.QUIZ,
            correct_option_id=data["correct"],
            explanation=data["explanation"], is_anonymous=False,
        )
        bump("quizzes")
    else:
        msg  = await update.message.reply_text("⏳")
        data = await gen_quiz()
        sent = await update.message.chat.send_poll(
            question="🧠 " + data["question"],
            options=data["options"], type=Poll.QUIZ,
            correct_option_id=data["correct"],
            explanation=data["explanation"], is_anonymous=False,
        )
        bump("quizzes")
        await msg.delete()

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html(
        "📚 <b>Команди</b>\n━━━━━━━━━━━━━━━\n"
        "/word — слово прямо зараз (+15 XP)\n"
        "/quiz — quiz з варіантами\n"
        "/stats — твій профіль і прогрес\n"
        "/top — лідерборд ТОП-10\n"
        "/notips — вимкнути поради\n"
        "/tips — увімкнути поради\n\n"
        "💬 Або просто пиши питання про англійську!"
    )

async def cmd_notips(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    with db() as c: c.execute("UPDATE users SET tips_on=0 WHERE user_id=?", (update.effective_user.id,))
    await update.message.reply_text("🔕 Поради вимкнено. /tips — увімкнути")

async def cmd_tips_on(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    with db() as c: c.execute("UPDATE users SET tips_on=1 WHERE user_id=?", (update.effective_user.id,))
    await update.message.reply_text("✅ Поради увімкнено! 💡")

async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    today = str(date.today())
    with db() as c:
        total  = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        active = c.execute("SELECT COUNT(*) FROM users WHERE last_active=?", (today,)).fetchone()[0]
        s      = c.execute("SELECT messages,new_u,quizzes FROM daily_stats WHERE dt=?", (today,)).fetchone() or (0,0,0)
        top3   = c.execute("SELECT first_name,xp,streak FROM users ORDER BY xp DESC LIMIT 3").fetchall()
        avg_xp = c.execute("SELECT AVG(xp) FROM users").fetchone()[0] or 0
        no_tips= c.execute("SELECT COUNT(*) FROM users WHERE tips_on=0").fetchone()[0]
    t3 = "\n".join([f"  {i+1}. {r[0]} — {r[1]}XP 🔥{r[2]}" for i,r in enumerate(top3)])
    await update.message.reply_html(
        f"🛠 <b>АДМІН ПАНЕЛЬ — {today}</b>\n━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Всього юзерів: <b>{total}</b>\n"
        f"✅ Активних сьогодні: <b>{active}</b>\n"
        f"⭐ Середній XP: {avg_xp:.0f}\n"
        f"🔕 Вимкнули поради: {no_tips}\n\n"
        f"📊 <b>Сьогодні:</b>\n"
        f"  💬 Повідомлень: {s[0]}\n"
        f"  🆕 Нових юзерів: {s[1]}\n"
        f"  🧠 Quiz: {s[2]}\n\n"
        f"🏆 <b>ТОП-3:</b>\n{t3}"
    )

# ─── CALLBACKS ─────────────────────────────────────────────
async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    await q.answer()
    uid  = q.from_user.id
    name = q.from_user.first_name or "друже"
    upsert_user(uid, q.from_user.username or "", name)

    match q.data:
        case "start_ok":
            await q.message.reply_html(
                f"🚀 <b>Відмінно, {name}!</b>\n"
                "Чекай ранкового посту о <b>9:00</b>!\n"
                "А зараз — /word щоб отримати перше слово 💪"
            )
        case "how_it_works":
            await q.message.reply_html(
                "ℹ️ <b>Як це працює:</b>\n\n"
                "⏰ <b>9:00</b> — слово/фраза/граматика\n"
                "☀️ <b>13:00</b> — цікавий факт або виклик\n"
                "💡 <b>15:00</b> — порада дня (можна вимкнути)\n"
                "🌙 <b>19:00</b> — вечірнє повторення\n\n"
                "🎮 <b>Заробляй XP:</b>\n"
                "• /word → +15 XP\n"
                "• Активність → +2 XP\n"
                "• Кнопки → +10 XP\n\n"
                "/stats — твій прогрес | /top — лідерборд"
            )
        case "my_stats":
            d = get_user(uid)
            if d:
                await q.message.reply_html(
                    f"📊 {rank(d['xp'])} | ⭐{d['xp']} XP | {sbar(d['streak'])} | {lives_str(d['lives'])}"
                )
        case "leaderboard":
            with db() as c:
                rows = c.execute("SELECT first_name,xp FROM users ORDER BY xp DESC LIMIT 5").fetchall()
            medals = ["🥇","🥈","🥉","4.","5."]
            await q.message.reply_html(
                "🏆 <b>ТОП-5</b>\n" +
                "\n".join(f"{medals[i]} {r[0]} — {r[1]} XP" for i,r in enumerate(rows))
            )
        case "got_it":
            add_xp(uid, 10)
            badges = check_badges(uid)
            extra  = (" 🎖 " + " ".join(badges)) if badges else ""
            await q.message.reply_html(f"✅ <b>{name}</b>, молодець! +10 XP{extra} 🚀")
        case "explain_more":
            await q.message.reply_html(f"📖 {name}, напиши питання — поясню детальніше 😊")
        case "more_word":
            msg  = await q.message.reply_text("⏳")
            text = await ask_max("Одне корисне B1 слово: переклад + 1 приклад. Коротко. HTML.", 250)
            add_xp(uid, 10, word=True)
            await msg.edit_text(text + "\n\n+10 XP", parse_mode="HTML")
        case "tips_off":
            with db() as c: c.execute("UPDATE users SET tips_on=0 WHERE user_id=?", (uid,))
            await q.message.reply_text("🔕 Поради вимкнено. /tips — увімкнути")
        case "tips_like":
            add_xp(uid, 5)
            await q.answer("👍 +5 XP!", show_alert=False)

# ─── MESSAGES ──────────────────────────────────────────────
TRIGGERS = ["як сказати","як перекласти","що означає","як правильно",
            "англійською","english","слово","переклад","помилка",
            "граматика","вимова","ідіом","фраза","переклади"]

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    u = update.effective_user
    if u.is_bot: return
    upsert_user(u.id, u.username or "", u.first_name or "")
    add_xp(u.id, 2)
    bump("messages")

    txt = update.message.text.lower()

    if is_group(update):
        me         = (await ctx.bot.get_me()).username.lower()
        is_reply   = (update.message.reply_to_message and
                      update.message.reply_to_message.from_user and
                      update.message.reply_to_message.from_user.username and
                      update.message.reply_to_message.from_user.username.lower() == me)
        is_mention = f"@{me}" in txt
        is_q       = txt.strip().endswith("?")
        has_trig   = any(w in txt for w in TRIGGERS)
        if not any([is_reply, is_mention, is_q, has_trig]):
            if random.random() > 0.07: return

    reply  = await ask_max(update.message.text)
    badges = check_badges(u.id)
    extra  = ("\n\n🎖 <b>Нове досягнення:</b> " + " ".join(badges)) if badges else ""
    await update.message.reply_html(reply + extra)

# ─── SCHEDULER ─────────────────────────────────────────────
async def post_group(app, text: str, kb=None):
    await app.bot.send_message(GROUP_ID, text, parse_mode="HTML",
                               **({"reply_markup": kb} if kb else {}))

async def daily_admin_report(app):
    try:
        today = str(date.today())
        with db() as c:
            total  = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            active = c.execute("SELECT COUNT(*) FROM users WHERE last_active=?", (today,)).fetchone()[0]
            s      = c.execute("SELECT messages,new_u,quizzes FROM daily_stats WHERE dt=?", (today,)).fetchone() or (0,0,0)
        await app.bot.send_message(ADMIN_ID,
            f"📊 <b>Звіт {today}</b>\n"
            f"👥 Всього: {total} | Активних: {active}\n"
            f"💬 Повідомлень: {s[0]} | 🆕 Нових: {s[1]} | 🧠 Quiz: {s[2]}",
            parse_mode="HTML")
    except Exception as e:
        log.error(f"Admin report: {e}")

async def scheduler(app):
    done = set()
    while True:
        now = datetime.now()
        d, h, m = str(now.date()), now.hour, now.minute

        tasks = [
            (9,  0, "am",  lambda: gen(MORNING), kb_post()),
            (13, 0, "mid", lambda: gen(MIDDAY),  None),
            (15, 0, "tip", lambda: asyncio.coroutine(lambda: random.choice(TIPS))(), kb_tips()),
            (19, 0, "pm",  lambda: ask_max("Вечірній пост-повторення. Тепло. Виклик на завтра + факт. 'До зустрічі вранці 👋'", 400), None),
            (21, 0, "rep", daily_admin_report, None),
        ]

        for hh, mm, key, gen_fn, keyboard in tasks:
            tag = f"{key}_{d}"
            if h == hh and m == mm and tag not in done:
                try:
                    if key == "rep":
                        await gen_fn(app)
                    else:
                        if key == "tip":
                            text = random.choice(TIPS)
                        else:
                            text = await gen_fn()
                        await post_group(app, text, keyboard)
                    done.add(tag)
                    log.info(f"✅ {key} пост відправлено")
                except Exception as e:
                    log.error(f"{key}: {e}")

        await asyncio.sleep(30)

# ─── MAIN ──────────────────────────────────────────────────
async def main():
    init_db()
    log.info("📦 DB OK")

    app = Application.builder().token(BOT_TOKEN).build()
    for cmd, fn in [
        ("start", cmd_start), ("stats", cmd_stats), ("top", cmd_top),
        ("word", cmd_word), ("quiz", cmd_quiz), ("help", cmd_help),
        ("notips", cmd_notips), ("tips", cmd_tips_on), ("admin", cmd_admin),
    ]:
        app.add_handler(CommandHandler(cmd, fn))

    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    log.info("✅ Макс онлайн 🚀 | 9:00 / 13:00 / 15:00 / 19:00 / 21:00")

    asyncio.create_task(scheduler(app))
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
