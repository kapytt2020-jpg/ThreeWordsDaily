#!/bin/bash
# ══════════════════════════════════════════
#  ThreeWordsDaily BOT — Quick Start
#  Run all bots in parallel background tabs
# ══════════════════════════════════════════

cd "$(dirname "$0")"

echo "🚀 ThreeWordsDaily BOT — Starting..."
echo ""

# Check .env exists
if [ ! -f .env ]; then
  echo "❌ .env not found! Copy .env.example and fill in your tokens."
  exit 1
fi

# Start each bot in background
echo "▶️  Starting learning_bot.py..."
python3 learning_bot.py &
PID1=$!

echo "▶️  Starting content_publisher.py..."
python3 content_publisher.py &
PID2=$!

echo "▶️  Starting analyst_bot.py..."
python3 analyst_bot.py &
PID3=$!

echo "▶️  Starting teacher_bot.py..."
python3 teacher_bot.py &
PID4=$!

echo ""
echo "✅ All bots running!"
echo "   learning_bot    PID: $PID1"
echo "   content_bot     PID: $PID2"
echo "   analyst_bot     PID: $PID3"
echo "   teacher_bot     PID: $PID4"
echo ""
echo "Press Ctrl+C to stop all bots"

# Wait and kill all on Ctrl+C
trap "echo ''; echo '🛑 Stopping all bots...'; kill $PID1 $PID2 $PID3 $PID4 2>/dev/null; exit 0" INT
wait
