# ThreeWordsDaily — Повний гайд по налаштуванню

## 📁 Де що знаходиться

| Сервіс | URL | Навіщо |
|--------|-----|--------|
| n8n | https://youtubeeee.app.n8n.cloud | Мозок — запускає всі workflow |
| GitHub | https://github.com/kapytt2020-jpg/ThreeWordsDaily | Код і workflow файли |
| Google Sheets | https://docs.google.com/spreadsheets/d/14F-C1iOLIuTRoNUpluZATYMzVtNbfWSFUcrRgijHhiQ | База даних онлайн |
| Telegram | @ThreeWordsDailyChat | Головний канал |

## 🤖 4 Workflow в n8n

| Файл | Назва | Що робить | Розклад |
|------|-------|-----------|---------|
| workflow_fixed.json | Головний бот | Контент + відповіді юзерам | 9:00, 13:00, 18:00, 19:00, 20:00 |
| workflow_analytics.json | Аналітика | Аналіз 8 конкурентів | Щопонеділка 10:00 |
| workflow_promo.json | Промо (n8n) | Пости в групи через бот | Щосереди 12:00 |
| promo_telethon.py | Промо (Python) | Пости від USER-акаунту | Запускати вручну або cron |

## 🔑 Credentials в n8n

| Назва | Тип | Значення |
|-------|-----|---------|
| telegramApi | Telegram API | 8350734666:AAFhKT7Pdq1PLTE3erIs5y_o3v2eOW4mXZs |
| openAiApi | OpenAI API | sk-proj-Yr9pSoWtYCL2Jmb... |
| googleSheetsOAuth2Api | Google Sheets OAuth2 | Через OAuth login |

## 📊 Google Sheets — вкладки

| Вкладка | Зберігає |
|---------|---------|
| Users | user_id, xp, streak, level, last_active |
| Competitors | Дані конкурентів щотижня |
| PromoStats | Куди постили і коли |

## 🐍 Telethon промо (promo_telethon.py)

```bash
pip3 install telethon
python3 promo_telethon.py
```

Потрібно додати в файл:
- API_ID: 39641928
- API_HASH: (з my.telegram.org/apps)
- PHONE: твій номер +380XXXXXXXXX

## 📱 Telegram боти

| Бот | Token | Призначення |
|-----|-------|-------------|
| @Clickecombot | 8350734666:... | ГОЛОВНИЙ — відповідає юзерам |
| @YourBot_test_bot | 8639302828:... | Тестовий |
| @YourBot_prod_bot | 8681431935:... | Продакшн |
| @SpeakBetterrbot | 8625727121:... | PR бот |

## ✅ Чеклист запуску

- [ ] telegramApi credential в n8n
- [ ] openAiApi credential в n8n
- [ ] googleSheetsOAuth2Api credential в n8n
- [ ] workflow_fixed.json — імпортовано і ACTIVE
- [ ] workflow_analytics.json — імпортовано і ACTIVE
- [ ] workflow_promo.json — імпортовано і ACTIVE
- [ ] Google Sheets — вкладки Users, Competitors, PromoStats створені
- [ ] Admin chat_id вставлено в звітні ноди
- [ ] promo_telethon.py — api_hash вставлено
- [ ] Тест: /start в @Clickecombot відповів
