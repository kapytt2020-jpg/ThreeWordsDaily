# Scout Bot Setup — Automated Student Finder

The scout bot monitors Telegram groups for people who want to learn English
and replies organically with a recommendation for our bot.

## Prerequisites

1. Install telethon:
```
pip install telethon
```

2. Get Telegram API credentials (free):
   - Go to https://my.telegram.org/apps
   - Create an app → copy `api_id` and `api_hash`

3. Add to `.env`:
```
SCOUT_API_ID=12345678
SCOUT_API_HASH=abcdef1234567890abcdef
SCOUT_SESSION=scout_session
SCOUT_WATCH_GROUPS=ukrainian_learners,english_ua,learneng_ua,it_ukr
LEARNING_BOT_USERNAME=ThreeWordsDailyBot
TELEGRAM_CHAT_INVITE=t.me/+YourGroupInviteLink
```

## Groups to Monitor (add to SCOUT_WATCH_GROUPS)

Good target groups (public, English-learning):
- Groups named like: english_ua, learn_english_ukraine, anglijska_mova
- IT Ukrainian communities (devs want English)
- Emigration groups (people in EU need English)
- Student groups

## First Run (one-time auth)

```bash
cd ~/Desktop/ThreeWordsDaily_BOT
python3 scout_bot.py
# Enter your phone number when prompted
# Enter the Telegram code sent to your phone
# Session saved to scout_session.session
```

After first auth, the LaunchAgent runs it automatically.

## Rate Limits (built-in safety)

- Max 3 organic replies per hour
- Never replies to same person in same group twice
- 2-5 second natural delay before replying
- Never sends unsolicited DMs
- Only operates in whitelisted groups

## Trigger Phrases Monitored

Ukrainian: "хочу вчити англійську", "порадьте бот", "де вчити англійську"...
English: "want to learn english", "english bot recommend"...
