# ThreeWordsDaily — Production Architecture

## Active Production Files

| File | Role | Bot Token | Schedule |
|------|------|-----------|----------|
| `learning_bot.py` | Main user bot — commands + learning | LEARNING_BOT_TOKEN | 09:00, 12:00, 20:00 |
| `content_publisher.py` | Scheduled content posts | LEARNING_BOT_TOKEN | 13:00, 17:00 Fri, 18:00 Sun, 19:00 |
| `analytics_planner.py` | Metrics + weekly planning | (no bot, admin alerts only) | Every 15min, Sun 20:00 + 23:00 |
| `marketer_bot.py` | Outreach + lead capture | MARKETER_BOT_TOKEN | (event-driven only) |
| `teacher_bot.py` | Grammar assistant in group | teacher bot token | (event-driven only) |
| `analyst_bot.py` | Strategic analysis (admin) | analyst bot token | 08:00, 20:00 daily |
| `auto_promo.py` | Promo posts to external groups | Telethon user account | 10:00, 17:00 |
| `database.py` | Shared async SQLite module | — | — |

## Database: threewords.db (SQLite)

Tables managed by `database.py`:
- `users` — all user state
- `lessons_cache` — AI-generated lesson cache
- `progress_events` — event log
- `rewards` — badges

## Google Sheets Tables (optional sync layer)

| Sheet Tab | Writer | Reader |
|-----------|--------|--------|
| `users` | learning_bot.py | analytics_planner.py |
| `content_metrics` | content_publisher.py + analytics_planner.py | analytics_planner.py |
| `content_plan` | analytics_planner.py | content_publisher.py |
| `used_words` | analytics_planner.py | analytics_planner.py |
| `leads` | marketer_bot.py | (admin manual) |

## Telegram Bots in Use

| Token Env Var | Bot | Handles |
|---------------|-----|---------|
| LEARNING_BOT_TOKEN | Main learning bot | All user commands + group posts |
| MARKETER_BOT_TOKEN | Outreach bot | Private lead funnel only |
| teacher_bot token | Teacher | Grammar in group |
| analyst token | Analyst | Admin-only strategy |

## Scheduled Posts Timeline (Ukraine time)

```
09:00 — Word of the day [learning_bot.py]
12:00 — Daily quiz [learning_bot.py]
13:00 — Idiom of the day [content_publisher.py]
17:00 Fri — English fun fact [content_publisher.py]
18:00 Sun — Weekly quiz [content_publisher.py]
19:00 — Mini story [content_publisher.py]
20:00 — Evening motivation + streak reminder [learning_bot.py]
20:00 Sun — Weekly analytics report [analytics_planner.py]
23:00 Sun — Next week content plan [analytics_planner.py]
10:00 & 17:00 — External promo [auto_promo.py]
```

No two files post to the same chat at the same time.

## Archived Files

Moved to `_archive/` — do not reactivate:
- `bot.py` — merged into learning_bot.py
- `bot_main.py` — merged into learning_bot.py
- `ads_bot.py` — merged into marketer_bot.py
- `speak_bot.py` — merged into marketer_bot.py
- `content_extra.py` — merged into content_publisher.py
- `promo_telethon.py` — dead code, redundant with auto_promo.py
- `workflow_fixed.json` — duplicate n8n workflow
- `workflow_promo.json` — replaced by auto_promo.py

## Starting the Production System

```bash
# Terminal 1: Main learning bot
python learning_bot.py

# Terminal 2: Content publisher
python content_publisher.py

# Terminal 3: Analytics planner
python analytics_planner.py

# Terminal 4: Marketer bot (if outreach is active)
python marketer_bot.py

# Terminal 5: Teacher bot
python teacher_bot.py

# Terminal 6: Analyst bot (admin)
python analyst_bot.py

# Terminal 7: Promo agent
python auto_promo.py
```

Or use a process manager:
```bash
# With PM2
pm2 start learning_bot.py --interpreter python3
pm2 start content_publisher.py --interpreter python3
pm2 start analytics_planner.py --interpreter python3
```
