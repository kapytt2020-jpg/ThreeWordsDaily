# 🐰 ThreeWordsDaily — Version 1.0

> **Telegram бот + Mini App для щоденного вивчення англійської мови.**
> Автоматично надсилає слова, квізи, мотивацію — без жодної ручної роботи.
> Є компаньйон-пітомець (Mochi та інші), стікер-пак, аналітика.

---

## Зміст

1. [Що це таке?](#що-це-таке)
2. [Як працює автоматичний бот](#як-працює-автоматичний-бот)
3. [Повна структура проєкту](#повна-структура-проєкту)
4. [Швидкий старт (для чайників)](#швидкий-старт)
5. [Налаштування .env](#налаштування-env)
6. [Запуск всіх ботів](#запуск-всіх-ботів)
7. [Mini App (Telegram WebApp)](#mini-app)
8. [Стікери Mochi + LottieFiles](#стікери-mochi)
9. [Google Sheets інтеграція](#google-sheets)
10. [Розклад автоповідомлень](#розклад-автоповідомлень)
11. [Всі команди бота](#всі-команди-бота)
12. [Архітектура системи](#архітектура-системи)
13. [Часті питання](#часті-питання)

---

## Що це таке?

**ThreeWordsDaily** — система з 5 ботів + Telegram Mini App, яка:

- 📚 Щодня надсилає 3 нові англійські слова вашій групі (автоматично, без вашої участі)
- 🧠 Генерує квізи, ідіоми, міні-історії через OpenAI
- 🐾 Дає кожному користувачу власного пітомця-компаньйона (17+ персонажів)
- 📊 Відстежує XP, серії, прогрес кожного учасника
- 🎨 Має стікер-пак Mochi для Telegram
- 🤖 Аналізує активність і пропонує стратегії росту

---

## Як працює автоматичний бот

> **Це найважливіша частина.** Бот сам, без вашої участі, надсилає повідомлення у групу кожного дня.

### Що надсилається автоматично:

```
09:00 🌅  Слово дня + транскрипція + приклад (learning_bot.py)
12:00 🧠  Квіз-опитування (вгадай переклад)   (learning_bot.py)
13:00 💬  Ідіома дня                            (content_publisher.py)
17:00 🎉  Цікавий факт про англійську (пт)      (content_publisher.py)
18:00 📝  Тижневий квіз (нд)                    (content_publisher.py)
19:00 📖  Міні-історія з вивченими словами      (content_publisher.py)
20:00 🔥  Вечірня мотивація + нагадування стріку (learning_bot.py)
```

### Як це запустити (одна команда):

```bash
# Запускає всі боти одночасно у фоні
bash run.sh
```

Або кожен окремо:
```bash
python3 learning_bot.py        # головний бот (09:00 / 12:00 / 20:00)
python3 content_publisher.py   # контент (13:00 / 19:00)
python3 teacher_bot.py         # Лекс — граматика в групі
python3 analyst_bot.py         # аналітика для адміна
python3 marketer_bot.py        # онбординг + реферали
```

Управління процесами:
```bash
bash run.sh start    # запустити всі боти у фоні
bash run.sh stop     # зупинити всі
bash run.sh status   # перевірити стан
bash run.sh logs learning_bot  # дивитись логи конкретного бота
bash run.sh restart  # перезапустити всі
```

**Бот працює 24/7 поки запущений Python процес.** На Mac/Linux можна запустити через `screen` або `launchd`.

---

## Повна структура проєкту

```
ThreeWordsDaily_BOT/
│
├── 🤖 БОТИ (Python файли)
│   ├── learning_bot.py          ← ГОЛОВНИЙ БОТ (слова, квізи, мотивація)
│   ├── content_publisher.py     ← ПУБЛІКАТОР (ідіоми, факти, міні-сторії)
│   ├── analytics_planner.py     ← ПЛАНУВАЛЬНИК (метрики кожні 15хв)
│   ├── analyst_bot.py           ← БОТ-АНАЛІТИК (для адміна) [+retention, +top10, +curriculum, +weekly]
│   ├── teacher_bot.py           ← ВЧИТЕЛЬ Лекс (граматика в групі)
│   ├── marketer_bot.py          ← МАРКЕТЕР (онбординг + реферальна система)
│   └── mochi_sticker_bot.py     ← СТІКЕРИ (створення пакету в Telegram)
│
├── 📚 НАВЧАЛЬНИЙ КОНТЕНТ
│   └── content_plan_9months.py  ← 9-МІСЯЧНИЙ ПЛАН (квітень–грудень, 36 тижнів, 540 слів)
│
├── 🗄️ БАЗА ДАНИХ
│   └── database.py              ← всі SQL-запити (SQLite, async)
│
├── 📱 MINI APP (Telegram WebApp)
│   └── miniapp/
│       ├── api.py               ← FastAPI бекенд (ендпоінти /api/*)
│       ├── app.js               ← весь UI (17 компаньйонів, урок, квіз)
│       ├── style.css            ← весь CSS (персонажі, анімації)
│       ├── index.html           ← точка входу
│       ├── mochi_sticker.html   ← інтерактивний Мочі (9 виразів)
│       ├── preview10.html       ← вибір компаньйона (27 персонажів)
│       └── vercel.json          ← деплой на Vercel
│
├── ⚙️ КОНФІГУРАЦІЯ
│   ├── .env                     ← СЕКРЕТИ (токени, ключі) — НЕ в git!
│   ├── .env.example             ← шаблон .env
│   └── requirements.txt         ← Python залежності
│
├── 📦 АРХІВ (старі версії)
│   └── _archive/                ← 10 старих файлів (не видаляти!)
│
└── 📋 ДОКУМЕНТАЦІЯ
    ├── README.md                ← цей файл
    ├── ARCHITECTURE.md          ← технічна архітектура
    └── PRODUCTION_ARCHITECTURE.md
```

---

## Швидкий старт

### Що потрібно (передумови):

- [ ] Python 3.11+
- [ ] Аккаунт Telegram + бот (через @BotFather)
- [ ] OpenAI API ключ (platform.openai.com)
- [ ] Telegram группа/канал де бот буде адміном

### Крок 1 — Клонувати/отримати файли

```bash
cd ~/Desktop/ThreeWordsDaily_BOT
```

### Крок 2 — Встановити залежності

```bash
pip install -r requirements.txt
```

### Крок 3 — Налаштувати .env

```bash
cp .env.example .env
nano .env   # або відкрити в будь-якому текстовому редакторі
```

Заповнити всі значення (дивись розділ [Налаштування .env](#налаштування-env)).

### Крок 4 — Ініціалізувати базу даних

```bash
cd miniapp
python3 database.py
cd ..
```

Повинно вивести: `DB OK`

### Крок 5 — Запустити головний бот

```bash
python3 learning_bot.py
```

Якщо бачиш `Scheduled jobs registered: 09:00, 12:00, 20:00` — все працює! 🎉

---

## Налаштування .env

Відкрий файл `.env` та заповни:

```env
# ── Головний бот (learning_bot.py) ──
LEARNING_BOT_TOKEN=8681431935:AAG...     # токен від @BotFather

# ── Маркетер бот (marketer_bot.py) — окремий бот ──
MARKETER_BOT_TOKEN=другий_токен_тут

# ── Вчитель бот (teacher_bot.py) ──
TEACHER_BOT_TOKEN=третій_токен_тут

# ── Аналітик бот (analyst_bot.py) ──
ANALYST_BOT_TOKEN=четвертий_токен_тут

# ── ID Telegram групи куди постити ──
TELEGRAM_CHAT_ID=-1002680027938          # ID групи (від'ємне число!)

# ── Ваш особистий Telegram ID ──
ADMIN_CHAT_ID=6923740900                 # Знайди через @userinfobot

# ── OpenAI ──
OPENAI_API_KEY=sk-proj-...              # з platform.openai.com

# ── Google Sheets (необов'язково) ──
SHEETS_API_URL=                         # залиш пустим якщо не потрібно
```

### Як отримати TELEGRAM_BOT_TOKEN?
1. Відкрий @BotFather в Telegram
2. Напиши `/newbot`
3. Придумай назву та username для бота
4. Скопіюй токен який дасть BotFather

### Як отримати TELEGRAM_CHAT_ID?
1. Додай бота до групи як адміна
2. Напиши будь-що в групу
3. Відкрий: `https://api.telegram.org/bot<ТВІЙtoken>/getUpdates`
4. Знайди `"chat":{"id":` — це і є CHAT_ID (від'ємне число)

### Як отримати свій ADMIN_CHAT_ID?
1. Напиши @userinfobot в Telegram
2. Він скаже твій ID

---

## Запуск всіх ботів

### Варіант 1 — Один за одним (для тестування)

```bash
# Термінал 1 — головний бот
python3 learning_bot.py

# Термінал 2 — публікатор контенту
python3 content_publisher.py

# Термінал 3 — аналітик (для адміна)
python3 analyst_bot.py

# Термінал 4 — вчитель в групі
python3 teacher_bot.py
```

### Варіант 2 — Всі у фоні через screen (рекомендовано)

```bash
# Встановити screen якщо не має
brew install screen   # Mac
# або: apt install screen  (Linux)

# Запустити кожен бот у окремому screen
screen -S learning  -dm python3 learning_bot.py
screen -S publisher -dm python3 content_publisher.py
screen -S analyst   -dm python3 analyst_bot.py
screen -S teacher   -dm python3 teacher_bot.py

# Перевірити що всі запущені
screen -ls
```

```
# Підключитись до логів
screen -r learning    # дивитись логи learning_bot
# Ctrl+A, D — відключитись (бот продовжує працювати)
```

### Варіант 3 — Автозапуск при старті Mac (launchd)

Файл вже є в `~/Library/LaunchAgents/`. Або:

```bash
# Запустити через launchctl
launchctl load ~/Library/LaunchAgents/com.threewordsbot.learning.plist
```

### Варіант 4 — Один скрипт run.sh

Якщо файл `run.sh` є в папці:
```bash
bash run.sh
```

---

## Mini App

Telegram Mini App — це веб-додаток який відкривається прямо в Telegram.

### Що вміє Mini App:
- 🥚 Анімація вилуплення яйця при першому вході
- 🐾 Вибір компаньйона (17 персонажів + можливість змінити одяг)
- 📚 Щоденний урок (3 слова + ідіома + міні-сторія)
- 🧠 Квіз по словам
- 📊 Профіль з XP, стрік, рейтинг
- 🏆 Таблиця лідерів

### Де живе:
- Фронтенд: `miniapp/` (HTML/CSS/JS)
- Бекенд: `miniapp/api.py` (FastAPI)
- Деплой: Vercel (автоматично при push на GitHub)

### Як запустити локально:
```bash
cd miniapp
pip install fastapi uvicorn openai python-dotenv httpx
uvicorn api:app --reload --port 8000
```
Відкрий: `http://localhost:8000`

### Деплой на Vercel:
```bash
# Потрібен Vercel CLI
npm install -g vercel
cd miniapp
vercel --prod
```

### Підключення до Telegram:
1. У @BotFather: `/newapp` або `/setmenubutton`
2. Вкажи URL: `https://threewords-app.vercel.app`
3. Кнопка "Відкрити" з'явиться в боті

---

## Стікери Mochi

### Що є:
- `miniapp/mochi_sticker.html` — інтерактивний Мочі з 9 виразами
- `mochi_sticker_bot.py` — автоматичне створення пакету стікерів

### Крок 1 — Переглянь інтерактивного Мочі

Відкрий файл у браузері:
```
ThreeWordsDaily_BOT/miniapp/mochi_sticker.html
```

Там є:
- 9 кнопок виразів (😊 💕 😴 😮 🌟 😢 😤 😉)
- Натисни на Мочі — він реагує
- Тримай — з'являються серденька
- Кнопка **🎬 Записати** — завантажує WebM відео

### Крок 2 — Зроби анімовані стікери через LottieFiles

1. Зайди на **https://app.lottiefiles.com** (ти вже залогінений ✅)
2. Натисни **"Create"** → **"Blank animation"** або **"Use AI"**
3. Завантаж SVG або PNG Мочі (або використай WebM з кроку 1)
4. Зроби анімацію (3 сек, 512×512)
5. Скачай як **.tgs** (Telegram Sticker format) — кнопка Export → Telegram

**АБО (простіший шлях):**

1. На LottieFiles: **"Lottie to TGS"** конвертер
2. Або використай їх **Community** — там є безкоштовні готові Lottie анімації
3. Знайди cute rabbit / bunny → завантаж `.tgs`

### Крок 3 — Завантаж стікери в Telegram

**Спосіб A — через @Stickers бот:**
1. Відкрий @Stickers в Telegram
2. `/newpack` — новий пакет
3. Надішли `.png` файл (512×512) або `.tgs` (animated)
4. Відповідь на запит emoji
5. `/publish` — пакет готовий!

**Спосіб B — автоматично через скрипт:**
```bash
# Крок 1: встановити Playwright
pip install playwright
playwright install chromium

# Крок 2: зробити 9 PNG стікерів (512×512) з HTML
python3 mochi_sticker_bot.py --export

# Крок 3: завантажити в Telegram
python3 mochi_sticker_bot.py --upload
```
Після цього буде посилання: `t.me/addstickers/mochi_threewords_by_<ім'я_бота>`

### Як зробити що стікер реагує при натисканні в чаті?

Telegram підтримує **інтерактивні стікери** у форматі `.tgs` (Lottie анімація):
- Стікер автоматично програє анімацію при відправці
- При натисканні на великий стікер у чаті — відбувається ефект (лише в преміум)
- Для базової інтерактивності достатньо анімованого `.tgs`

**Для повної інтерактивності (тап = нова анімація):**
> Це Telegram Premium feature для великих emoji. Для звичайних стікерів — достатньо `.tgs` з гарною loop-анімацією.

---

## Google Sheets

Google Sheets використовується як зручний backup для даних (необов'язково).

### Таблиці які синхронізуються:

| Лист | Що зберігає |
|------|------------|
| `users` | user_id, xp, streak, level, words_learned |
| `content_plan` | план контенту на тиждень |
| `used_words` | які слова вже використовувались |
| `leads` | нові юзери від marketer_bot |
| `content_metrics` | охоплення, реакції на пости |

### Як підключити:

1. Відкрий Google Sheets — створи нову таблицю
2. Розширення → Apps Script → вставити код:

```javascript
function doPost(e) {
  var data = JSON.parse(e.postData.contents);
  var sheet = SpreadsheetApp.getActiveSpreadsheet()
    .getSheetByName(data.sheet || "users");

  if (data.action === "append") {
    var row = Object.values(data.row);
    sheet.appendRow(row);
  } else if (data.action === "update") {
    // знайти рядок по user_id та оновити
    var id = data.row.user_id;
    var rows = sheet.getDataRange().getValues();
    for (var i = 1; i < rows.length; i++) {
      if (rows[i][0] == id) {
        sheet.getRange(i+1, 1, 1, Object.values(data.row).length)
          .setValues([Object.values(data.row)]);
        break;
      }
    }
  }
  return ContentService.createTextOutput("OK");
}
```

3. Деплой → New deployment → Web App → Anyone
4. Скопіюй URL → встав в `.env` як `SHEETS_API_URL`

---

## Розклад автоповідомлень

Ось повний розклад всього що надсилається автоматично (Київський час):

| Час | Що надсилається | Файл | Куди |
|-----|----------------|------|------|
| **09:00** щодня | 🌅 Слово дня + транскрипція + приклад | `learning_bot.py` | Група |
| **12:00** щодня | 🧠 Квіз-опитування (4 варіанти) | `learning_bot.py` | Група |
| **13:00** щодня | 💬 Ідіома дня з перекладом | `content_publisher.py` | Група |
| **17:00** п'ятниця | 🎉 Цікавий факт про англійську | `content_publisher.py` | Група |
| **18:00** неділя | 📝 Тижневий квіз (5 питань) | `content_publisher.py` | Група |
| **19:00** щодня | 📖 Міні-сторія з вивченими словами | `content_publisher.py` | Група |
| **20:00** щодня | 🔥 Мотивація + нагадування стрік | `learning_bot.py` | Група |
| **08:00** щодня | 📊 Авто-аналіз для адміна | `analyst_bot.py` | Адмін |
| **20:00** щодня | 📊 Авто-аналіз для адміна | `analyst_bot.py` | Адмін |
| Кожні 15хв | 📈 Знімок метрик → Sheets | `analytics_planner.py` | Sheets |
| Неділя 20:00 | 📋 Тижневий звіт | `analytics_planner.py` | Адмін |
| Неділя 23:00 | 🗓️ План контенту на тиждень | `analytics_planner.py` | Sheets |

> **Важливо:** Жоден час не перетинається між `learning_bot.py` та `content_publisher.py`. Конфліктів постів немає.

---

## Всі команди бота

Юзери пишуть ці команди боту в особистих повідомленнях або в групі:

| Команда | Що робить |
|---------|-----------|
| `/start` | Привітання, реєстрація, вибір рівня |
| `/help` | Список команд |
| `/word` | Отримати нове слово зараз |
| `/quiz` | Пройти міні-квіз зараз |
| `/stats` | Мій XP, стрік, рівень |
| `/profile` | Детальний профіль + компаньйон |
| `/lessons` | Повний урок (3 слова + ідіома + сторія) |
| `/top` | Топ-10 по XP |
| `/save` | Зберегти поточне слово |
| `/review` | Повторити збережені слова |
| `/mywords` | Список всіх збережених слів |
| `/invite` | Реферальне посилання |

### Команди аналітик-бота (тільки адмін):

| Команда | Що робить |
|---------|-----------|
| `/stats` | Статистика групи зараз |
| `/ideas` | Ідеї контенту на завтра |
| `/growth` | 3 поради для росту |
| `/report` | Повний аналітичний звіт |

---

## Архітектура системи

```
┌─────────────────────────────────────────────────────────────────┐
│                    THREEWORDSDAILY v1.0                         │
└─────────────────────────────────────────────────────────────────┘

TELEGRAM GROUP (@ThreeWordsDailyChat)
    ↑ posts at 09:00/12:00/13:00/19:00/20:00
    │
    ├── [learning_bot.py]      → handles /commands + schedules 09:00/12:00/20:00
    ├── [content_publisher.py] → schedules 13:00/17:00Fri/18:00Sun/19:00
    └── [teacher_bot.py]       → responds to grammar questions in group

USERS (private chat with bot)
    ↑↓ /start /word /quiz /stats /profile /lessons
    │
    └── [learning_bot.py] → saves XP/streak/words to SQLite

TELEGRAM MINI APP (webapp button in bot)
    ↑↓ opens in Telegram
    │
    ├── [miniapp/app.js]   → UI: egg hatch → pick companion → daily lesson
    └── [miniapp/api.py]   → FastAPI backend on Vercel

ADMIN (private chat)
    ↑ receives auto-reports 08:00 / 20:00
    │
    └── [analyst_bot.py]  → /stats /ideas /growth /report

NEW USERS (outreach)
    │
    └── [marketer_bot.py] → funnels users to group + mini app

DATABASE
    └── miniapp/threewords.db  (SQLite)
        ├── users              (xp, streak, level, words_learned, pet)
        ├── lessons_cache      (cached AI lessons)
        ├── progress_events    (event log)
        └── rewards            (badges)

ANALYTICS (background)
    └── [analytics_planner.py]
        ├── every 15min → snapshot metrics
        ├── Sunday 20:00 → weekly report
        └── Sunday 23:00 → content plan
```

### Токени ботів (всі окремі):

| Бот | Змінна в .env | Призначення |
|-----|--------------|-------------|
| Головний бот | `LEARNING_BOT_TOKEN` | Юзери, команди, пости |
| Маркетер | `MARKETER_BOT_TOKEN` | Нові юзери, лідогенерація |
| Вчитель | `TEACHER_BOT_TOKEN` | Граматика в групі |
| Аналітик | `ANALYST_BOT_TOKEN` | Репорти для адміна |

---

## Часті питання

### ❓ Бот не надсилає повідомлення в групу

**Перевір:**
1. Бот є адміном групи (Settings → Administrators → додати бота)
2. `TELEGRAM_CHAT_ID` правильний (від'ємне число, наприклад `-1002680027938`)
3. Процес `learning_bot.py` запущений і не завис

```bash
# Перевірити чи бот бачить групу
# Відкрий у браузері (замінити TOKEN):
https://api.telegram.org/bot<TOKEN>/getChat?chat_id=<CHAT_ID>
```

---

### ❓ OpenAI повертає помилку

**Перевір:**
1. Ключ `OPENAI_API_KEY` правильний (починається з `sk-proj-`)
2. Є кредити на рахунку (platform.openai.com → Billing)
3. Модель `gpt-4o-mini` доступна на вашому плані

---

### ❓ Як додати нового компаньйона?

1. Додай CSS арт у `miniapp/style.css` (дивись приклади lumix, kitsune, etc.)
2. Додай в `CHARACTERS` масив у `miniapp/app.js`
3. Додай builder функцію `buildXxxHTML(stageIdx)` в `app.js`
4. Додай в `VALID_CHARS` у `miniapp/api.py`

---

### ❓ Як оновити Mini App на Vercel?

```bash
cd miniapp
vercel --prod
```
Або push на GitHub якщо підключений auto-deploy.

---

### ❓ Як зупинити всі боти?

```bash
# Якщо запущені через screen
screen -r learning   # Ctrl+C, потім 'exit'
screen -r publisher  # Ctrl+C, потім 'exit'

# Якщо через launchctl
launchctl unload ~/Library/LaunchAgents/com.threewordsbot.*.plist

# Жорстко (вбити всі python3 процеси)
pkill -f "python3.*bot.py"
```

---

### ❓ Де зберігаються дані юзерів?

Всі дані в SQLite базі: `miniapp/threewords.db`

```bash
# Подивитись базу
sqlite3 miniapp/threewords.db
.tables              # список таблиць
SELECT * FROM users LIMIT 5;   # перші 5 юзерів
.quit
```

---

### ❓ Бот перестав відповідати на команди

```bash
# Перевірити лог
tail -f api.log
# або
screen -r learning   # дивитись живий лог
```

Зазвичай причина: кончились OpenAI кредити або Telegram заблокував токен (якщо бот crashнув з помилкою).

---

## Файли які НЕ треба чіпати

- `miniapp/threewords.db` — база даних (не видаляти!)
- `.env` — секрети (не комітити в git!)
- `_archive/` — старі версії (залишити для backup)
- `browser/` — кеш браузера (не чіпати)

---

## Версія 1.0 — Статус компонентів

| Компонент | Статус | Файл |
|-----------|--------|------|
| Головний бот | ✅ Готовий | `learning_bot.py` |
| Автопости 09:00/12:00/20:00 | ✅ Готові | `learning_bot.py` |
| Автопости 13:00/19:00 | ✅ Готові | `content_publisher.py` |
| База даних | ✅ Готова | `database.py` |
| Mini App UI | ✅ Готова | `miniapp/app.js` |
| Mini App API | ✅ Готова | `miniapp/api.py` |
| 17 компаньйонів | ✅ Готові | `miniapp/app.js` |
| Анімація яйця | ✅ Готова | `miniapp/app.js` |
| Mochi стікери | ✅ Готовий preview | `miniapp/mochi_sticker.html` |
| Telegram стікер-пак | 🔧 Потрібен Playwright | `mochi_sticker_bot.py` |
| Аналітик бот | ✅ Готовий | `analyst_bot.py` |
| Вчитель бот | ✅ Готовий | `teacher_bot.py` |
| Маркетер бот | ✅ Готовий | `marketer_bot.py` |
| Google Sheets | ⚙️ Опціональний | (інтеграція через `SHEETS_API_URL`) |

---

## Підтримка та розвиток

- Telegram: @ThreeWordsDailyChat
- Приклад Mini App: https://threewords-app.vercel.app
- Стікери: після `mochi_sticker_bot.py --upload`

---

*ThreeWordsDaily v1.0 — Зроблено з ❤️ для тих хто вчить англійську*
