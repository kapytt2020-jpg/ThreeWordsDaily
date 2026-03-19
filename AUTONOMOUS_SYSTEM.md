# ThreeWordsDaily — Autonomous Bot System

> Повністю автономна система: боти самі планують, генерують, аналізують і просувають контент.

---

## Архітектура системи

```
┌─────────────────────────────────────────────────────────┐
│                   TELEGRAM ECOSYSTEM                    │
│                                                         │
│  @ThreeWordsDailyChat    @YourBot_prod_bot              │
│       (канал)              (бот-вчитель)                │
│          │                      │                       │
│          └──────────┬───────────┘                       │
│                     ▼                                   │
│            [Mini App WebApp]                            │
│         Урок / Quiz / Tasks / Top                       │
└─────────────────────────────────────────────────────────┘
                      │
         ┌────────────┼────────────┐
         ▼            ▼            ▼
    [n8n Cloud]  [Python Bot]  [Telethon]
    Автоматизація  bot_main.py  promo_telethon.py
         │
    ┌────┴─────────────────────────────┐
    │  content_planner.py (неділя 23:00)│
    │  analytics.py      (неділя 20:00) │
    │  content_extra.py  (щодня)        │
    └───────────────────────────────────┘
         │
    [OpenAI GPT-4] → [Google Sheets DB]
```

---

## Файлова структура

```
ThreeWordsDaily_BOT/
├── bot_main.py              # Головний Python бот (повний UX)
├── content_extra.py         # Додатковий контент (idiom, story, quiz)
├── content_planner.py       # AI планувальник на тиждень
├── analytics.py             # Тижнева аналітика → адмін
├── promo_telethon.py        # Промо polls в групах (anti-ban)
├── .env                     # Токени та API ключі
├── credentials.local.json   # Токени всіх ботів
├── miniapp/
│   ├── index.html           # Telegram Mini App
│   ├── style.css            # Темна тема, gamification UI
│   └── app.js               # Логіка: уроки, quiz, streak, leaderboard
├── workflow_main.json        # n8n: основний workflow
├── workflow_promo.json       # n8n: авто промо
├── workflow_analytics.json   # n8n: аналітика
├── CONTENT_STYLE.md          # Аналіз 001k.Trade → наші шаблони
└── AUTONOMOUS_SYSTEM.md      # Цей файл
```

---

## Боти та їх ролі

| Бот | Токен | Роль |
|-----|-------|------|
| `@YourBot_prod_bot` | `8681431935:...` | Головний бот-вчитель, Mini App |
| `@YourBot_test_bot` | `8639302828:...` | Тестування |
| `@SpeakBetterrbot` | `8625727121:...` | PR бот, відповіді на згадки |
| `@YourBrand_group_teacher_bot` | `8619703324:...` | Вчитель в групах |
| User акаунт `+380982896457` | Telethon | Промо від людини |

---

## Завдання системи

### ✅ Завдання 1 — Контент поза 3 словами (`content_extra.py`)
```
09:00  3 слова (n8n)
13:00  Idiom дня + діалог
19:00  Mini-story зі словами тижня
Пт 17:00  Fun fact про англійську
Нд 18:00  Weekly quiz (5 polls)
```

### ✅ Завдання 2 — Автономне планування (`content_planner.py`)
- Запуск: кожна неділя о 23:00
- Аналізує використані слова та реакції
- AI генерує план на наступний тиждень
- Надсилає адміну на затвердження
- Google Sheets: таблиця `content_plan`

### ✅ Завдання 3 — Аналітика (`analytics.py`)
- Запуск: кожна неділя о 20:00
- Збирає: нових юзерів, retention 7d, streaks, топ-3
- AI дає інсайти та оцінку тижня
- Надсилає звіт адміну
- Google Sheets: таблиця `analytics`

### ✅ Завдання 4 — Автономна реклама (`promo_telethon.py`)
- Відправляє **Quiz Poll** замість тексту (менше банів)
- 5 різних poll тем, ротація
- Правильна відповідь → пояснення + лінк на бот
- Пауза 45-90 сек між групами

### ✅ Завдання 5 — Mini App (`miniapp/`)
- Telegram WebApp всередині бота
- Tabs: Урок / Завдання / Топ / Профіль
- Gamification: XP, streak, ранги, нагороди
- Задачі: щоденні з нагородами
- Leaderboard: топ тижня
- Персоналізація: рівень + тема

---

## Розклад автозапуску (cron)

```bash
# Додати в crontab (crontab -e):

# Idiom дня о 13:00
0 13 * * * cd ~/Desktop/ThreeWordsDaily_BOT && python3 content_extra.py

# Mini-story о 19:00
0 19 * * * cd ~/Desktop/ThreeWordsDaily_BOT && python3 content_extra.py

# Fun fact (п'ятниця 17:00)
0 17 * * 5 cd ~/Desktop/ThreeWordsDaily_BOT && python3 content_extra.py

# Weekly quiz (неділя 18:00)
0 18 * * 0 cd ~/Desktop/ThreeWordsDaily_BOT && python3 content_extra.py

# Аналітика (неділя 20:00)
0 20 * * 0 cd ~/Desktop/ThreeWordsDaily_BOT && python3 analytics.py

# Контент-план (неділя 23:00)
0 23 * * 0 cd ~/Desktop/ThreeWordsDaily_BOT && python3 content_planner.py

# Промо (понеділок, середа, п'ятниця о 11:00)
0 11 * * 1,3,5 cd ~/Desktop/BOT && python3 promo_telethon.py
```

---

## Env змінні (`.env`)

```env
OPENAI_API_KEY=sk-proj-...
TELEGRAM_BOT_TOKEN=8681431935:...
TELEGRAM_CHAT_ID=-1002680027938
ADMIN_CHAT_ID=6923740900
SHEETS_API_URL=                    # n8n webhook або Apps Script
```

---

## Mini App — деплой

### Варіант A — Vercel (рекомендовано, безкоштовно):
```bash
cd miniapp
npx vercel --prod
# Отримаєш URL типу: https://threewordsapp.vercel.app
```

### Варіант B — GitHub Pages:
```bash
# Просто пуш в /docs папку і включи GitHub Pages
```

### Після деплою — підключити до бота:
```bash
# В BotFather:
/setmenubutton → URL твого Mini App → "📚 Урок дня"
```

---

## Контент стиль (001k.Trade аналіз)

Детально в `CONTENT_STYLE.md`. Коротко:

| Принцип | Опис |
|---------|------|
| **Коротко** | 1-3 речення максимум |
| **Дані + думка** | Факт/слово + особистий коментар |
| **Insider tone** | "ми", "я знайшов", "спробуй" |
| **Мінімум CTA** | Кнопка, не текст "клікни" |
| **Емодзі** | 1-2, підсилюють, не прикрашають |

---

## Масштабування

### Фаза 1 (зараз): UA аудиторія
- `@ThreeWordsDailyChat` + `@YourBot_prod_bot`
- Мова інтерфейсу: українська

### Фаза 2: RU аудиторія
- `/start` → вибір мови 🇺🇦 / 🇷🇺
- Окремий канал: `@ThreeWordsDailyRU`
- Той самий бот, `bot_main.py` з `lang` параметром

### Фаза 3: EN аудиторія (глобал)
- Той самий підхід для вивчення іспанської / французької
- Масштабована архітектура вже готова

---

## Статус

| Компонент | Статус |
|-----------|--------|
| `bot_main.py` | ✅ Готово, тестовано |
| `promo_telethon.py` (polls) | ✅ Готово |
| `content_extra.py` | ✅ Готово, тестовано |
| `content_planner.py` | ✅ Готово, тестовано |
| `analytics.py` | ✅ Готово, тестовано |
| `miniapp/` | ✅ Готово, потрібен деплой |
| n8n local | ✅ Встановлено v2.8.4 |
| Google Sheets інтеграція | ⏳ Потрібен SHEETS_API_URL |
| Mini App деплой | ⏳ Потрібен Vercel/GitHub Pages |
| Cron автозапуск | ⏳ Потрібно налаштувати |

---

*Оновлено: Березень 2026*
