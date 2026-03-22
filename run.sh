#!/bin/bash
# Voodoo Platform — run all bots
# Usage: ./run.sh [bot_name|all]

set -euo pipefail
cd "$(dirname "$0")"

PYTHON=/opt/homebrew/bin/python3.14
LOG_DIR=logs
mkdir -p "$LOG_DIR"

start_bot() {
    local name="$1"
    local file="bots/${name}.py"
    if [ ! -f "$file" ]; then
        echo "❌ Not found: $file"
        return 1
    fi
    echo "▶ Starting $name..."
    nohup "$PYTHON" "$file" >> "$LOG_DIR/${name}.log" 2>&1 &
    echo "$!" > "$LOG_DIR/${name}.pid"
    echo "✅ $name started (PID $!)"
}

stop_bot() {
    local name="$1"
    local pid_file="$LOG_DIR/${name}.pid"
    if [ -f "$pid_file" ]; then
        local pid
        pid=$(cat "$pid_file")
        kill "$pid" 2>/dev/null && echo "⏹ $name stopped" || echo "⚠️ $name: PID $pid not found"
        rm -f "$pid_file"
    else
        pkill -f "bots/${name}.py" 2>/dev/null && echo "⏹ $name stopped" || echo "⚠️ $name not running"
    fi
}

BOTS=(
    voodoo_bot
    voodoo_speak_bot
    voodoo_teacher_bot
    voodoo_publisher_bot
    voodoo_analyst_bot
    voodoo_growth_bot
    voodoo_ops_bot
    voodoo_test_bot
)

case "${1:-all}" in
    all)
        for bot in "${BOTS[@]}"; do
            start_bot "$bot"
        done
        echo ""
        echo "✅ All Voodoo bots started"
        echo "Logs: $LOG_DIR/"
        ;;
    stop)
        for bot in "${BOTS[@]}"; do
            stop_bot "$bot"
        done
        ;;
    restart)
        for bot in "${BOTS[@]}"; do
            stop_bot "$bot"
        done
        sleep 1
        for bot in "${BOTS[@]}"; do
            start_bot "$bot"
        done
        ;;
    status)
        echo "🖥 Voodoo Bot Status"
        for bot in "${BOTS[@]}"; do
            if pgrep -f "bots/${bot}.py" > /dev/null; then
                echo "  ✅ $bot"
            else
                echo "  ❌ $bot"
            fi
        done
        ;;
    *)
        start_bot "$1"
        ;;
esac
