#!/bin/bash
# Debug log
echo "[$(date)] start_miniapp.sh starting" >> /Users/usernew/Desktop/ThreeWordsDaily_BOT/logs/miniapp_debug.log 2>&1
echo "PATH=$PATH" >> /Users/usernew/Desktop/ThreeWordsDaily_BOT/logs/miniapp_debug.log 2>&1
echo "HOME=$HOME" >> /Users/usernew/Desktop/ThreeWordsDaily_BOT/logs/miniapp_debug.log 2>&1
echo "PWD=$(pwd)" >> /Users/usernew/Desktop/ThreeWordsDaily_BOT/logs/miniapp_debug.log 2>&1

# Kill port 8000 if occupied
/usr/sbin/lsof -ti :8000 | xargs kill -9 2>/dev/null
sleep 1

cd /Users/usernew/Desktop/ThreeWordsDaily_BOT/miniapp
echo "[$(date)] Starting uvicorn..." >> /Users/usernew/Desktop/ThreeWordsDaily_BOT/logs/miniapp_debug.log 2>&1

exec /opt/homebrew/bin/python3.14 -m uvicorn api:app --host 0.0.0.0 --port 8000
