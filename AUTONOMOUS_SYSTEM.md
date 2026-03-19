# ThreeWordsDaily — Autonomous Learning System

## Мета

Система автономно генерує, планує, аналізує та просуває контент для 📚 вивчення англійської мови без ручного втручання.

## Архітектура

### 1️⃣ **Основний бот (@ThreeWordsDailyChat)**
Щодня надсилає контент в 3 часи:
- **08:00** — Слово дня + приклад
- **14:00** — Граматичне пояснення  
- **20:00** — Mini-story або практика

### 2️⃣ **Content Planner (workflow_content_planner.json)**
**Коли:** Кожну неділю в 23:00
**Що робить:**
- Аналізує які контент отримав найбільше реакцій
- AI генерує план на наступний тиждень
- Зберігає в Google Sheets таблицю `content_plan`

**План містить:**
```
День | Час | Тип | Тема | Слова | AI-промпт | Статус
------|------|------|------|------|-----------|-------
Пн | 08:00 | word | Business | entrepreneur | "Генерувати слово для бізнесу" | planned
Пн | 14:00 | grammar | Present Perfect | - | "Present Perfect для дій які почались у минулому" | planned
Пн | 20:00 | story | Job interview | present, career | "Story про інтерв'ю з 10 новими словами" | planned
```

### 3️⃣ **Workflow Execution (workflow_main_extended.json)**
Кожного дня:
1. Читає з таблиці `content_plan` що генерувати
2. Генерує контент через OpenAI GPT-4
3. Надсилає в чат користувачам
4. Логує реакції (👍 ❤️ 😀)

### 4️⃣ **Analytics Weekly (workflow_analytics.json)**
**Коли:** Кожну неділю в 10:00
**Збирає:**
- Нові користувачі: +15 на тиждень
- Retention (7 днів): 62%
- Топ слова за реакціями
- Streak статистика (максимум 120 днів)
- Таблиця `analytics` в Google Sheets

### 5️⃣ **Autonomous Promo (workflow_promo_autonomous.json)**
**Коли:** Автоматично кожні 3 дні
**База груп:**
```
Група | ID | Розмір | Статус | Дата_останньої_реклами
-------|-----|--------|--------|----------------------
Python_Lovers | 12345 | 2500 | ok | 2024-03-15
English_Learners | 67890 | 1200 | banned | 2024-02-20
```

**Як працює:**
- AI генерує текст залежно від типу групи (контент/дослідження/ігрова)
- Надсилає **Poll** (опитування) замість тексту — менше банів  
- Логує результат (sent/banned/error)
- Оновлює статус групи

## Типи контенту

### Щодня (3 основні сеанси)
| Час | Тип | Приклад | OpenAI Prompt |
|------|------|---------|---------------|
| 08:00 | **Word + Dialog** | *"entrepreneur"*  Приклад: "She's an entrepreneur" | Generate a common English word at CEFR A1-B2 level with 2 example dialogues |
| 14:00 | **Grammar Rule** | Present Perfect explanation (1 хв читання) | Explain one English grammar rule in 5 sentences for B1 learners |
| 20:00 | **Mini-Story** | Story використовуючи 5 слів тижня | Write a 100-word story using these 5 words: {words} |

### П'ятниця
| Тип | Опис |
|------|------|
| **Fun Fact** | Цікавий факт про англійську мову |
| **Quiz** | 5 запитань на слова тижня |

## Google Sheets Структура

### Таблиця 1: `content_plan` 
```
День | Час | Тип | Тема | Слова | AI_Prompt | Контент | Статус | Reactions
```

### Таблиця 2: `analytics`
```
Дата | Нові_юзери | Retention_7d | Топ_слово | Engagement | Quiz_пройденo
```

### Таблиця 3: `groups_promo`
```
Група_ID | Назва | Розмір | Статус | Дата_останньої | Результат
```

## n8n Workflows

| Workflow | Тригер | Функція |
|----------|--------|---------|
| **workflow_main_extended.json** | Cron: 08:00, 14:00, 20:00 | Генерує & надсилає контент |
| **workflow_content_planner.json** | Cron: Неділя 23:00 | Планує контент на тиждень |
| **workflow_analytics.json** | Cron: Неділя 10:00 | Збирає аналітику |
| **workflow_promo_autonomous.json** | Cron: Кожні 72 години | Автоматична реклама |

## Credentials потребу

```
✅ telegramApi — токен @Clickecombot
✅ openAiApi — n8n free OpenAI API credits
✅ googleSheetsOAuth2Api — доступ до Google Sheets
```

## Запуск системи

1. Імпортуй 4 workflow JSON файли в n8n
2. Активуй все
3. Чекай неділю 23:00 — перший план буде згенерований
4. Понеділок 08:00 — перший контент автоматично надійде

## Примітки

- Кожна Неділя → новий тиждень контенту
- AI автоматично аналізує реакції і підлаштовує складність
- Прово не спаму — користуємо Poll замість тексту
- Все логується в Google Sheets — легко監視

---

**Статус:** 🚀 Готово до запуску
**Дата:** 19.03.2026
