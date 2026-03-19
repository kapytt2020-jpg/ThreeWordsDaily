# Інструкція для Chrome AI — налаштування n8n

## КРОК 1 — Відкрий n8n
Перейди на: https://youtubeeee.app.n8n.cloud

## КРОК 2 — Додай Credentials

### Telegram (@Clickecombot — головний бот)
1. Зліва меню → Credentials → Add Credential
2. Тип: Telegram API
3. Назва: `telegramApi`
4. Token: `8350734666:AAFhKT7Pdq1PLTE3erIs5y_o3v2eOW4mXZs`
5. Save

### Telegram (@YourBot_test_bot)
1. Add Credential → Telegram API
2. Назва: `telegramApi - Test Bot`
3. Token: `8639302828:AAFIrusHQUiSii2cpnLwmifLA1rW5bpXIzE`
4. Save

### Telegram (@YourBot_prod_bot)
1. Add Credential → Telegram API
2. Назва: `telegramApi - Prod Bot`
3. Token: `8681431935:AAGGFw6AnGbs23_Wb2wRqZ4GM0WutK93wM0`
4. Save

### Telegram (@SpeakBetterrbot)
1. Add Credential → Telegram API
2. Назва: `telegramApi - SpeakBetter`
3. Token: `8625727121:AAGlC1lSvGsE8jpj2F8FTc7Hpc4cB0rgRt0`
4. Save

### Telegram (@YourBrand_group_teacher_bot)
1. Add Credential → Telegram API
2. Назва: `telegramApi - Teacher Bot`
3. Token: `8619703324:AAFm2FxZI5k-cIAd4...` ⚠️ НЕПОВНИЙ — пропусти

## КРОК 3 — Імпортуй workflow

1. Зліва → Workflows → Import
2. URL файлу: https://raw.githubusercontent.com/kapytt2020-jpg/ThreeWordsDaily/main/workflow_fixed.json
   АБО завантаж файл `workflow_fixed.json` і перетягни

## КРОК 4 — Підключи credentials до nodes

В імпортованому workflow:
1. Відкрий кожен Telegram вузол (червоний)
2. У полі Credential вибери `telegramApi`
3. Збережи

## КРОК 5 — Активуй workflow

Вгорі праворуч — перемикач Active → ON

## КРОК 6 — Імпортуй Analytics workflow

1. Workflows → Import
2. Завантаж: https://raw.githubusercontent.com/kapytt2020-jpg/ThreeWordsDaily/main/workflow_analytics.json
3. Знайди ноду "📤 Надіслати звіт адміну"
4. Встав свій Telegram chat_id в поле chatId
   (щоб дізнатись свій chat_id — напиши @userinfobot)
5. Активуй workflow

## КРОК 7 — Протестуй

Напиши боту @Clickecombot команду `/start`
Якщо відповів — все працює ✅
