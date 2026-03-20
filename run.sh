#!/usr/bin/env bash
# run.sh — Start all ThreeWordsDaily bots
# Usage: bash run.sh [stop|status|logs]
#
# Bots started:
#   learning_bot.py     — main daily-words bot
#   teacher_bot.py      — Лекс, group grammar assistant
#   analyst_bot.py      — admin analytics bot
#   marketer_bot.py     — growth / referral bot
#   content_publisher.py — scheduled content posts

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
PID_DIR="$SCRIPT_DIR/.pids"
PYTHON="${PYTHON:-python3}"

mkdir -p "$LOG_DIR" "$PID_DIR"

# ── Bot definitions ───────────────────────────────────────────────────────────

declare -A BOTS=(
    [learning_bot]="learning_bot.py"
    [teacher_bot]="teacher_bot.py"
    [analyst_bot]="analyst_bot.py"
    [marketer_bot]="marketer_bot.py"
    [content_publisher]="content_publisher.py"
)

# ── Helpers ───────────────────────────────────────────────────────────────────

start_bot() {
    local name="$1"
    local script="$2"
    local pid_file="$PID_DIR/${name}.pid"
    local log_file="$LOG_DIR/${name}.log"

    if [[ -f "$pid_file" ]]; then
        local pid
        pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            echo "  ⚠️  $name already running (pid $pid)"
            return
        fi
        rm -f "$pid_file"
    fi

    if [[ ! -f "$SCRIPT_DIR/$script" ]]; then
        echo "  ⏭️  $script not found — skipping"
        return
    fi

    cd "$SCRIPT_DIR"
    nohup "$PYTHON" "$script" >> "$log_file" 2>&1 &
    echo $! > "$pid_file"
    echo "  ✅ $name started (pid $!)"
}

stop_bot() {
    local name="$1"
    local pid_file="$PID_DIR/${name}.pid"

    if [[ ! -f "$pid_file" ]]; then
        echo "  ⏹️  $name not running"
        return
    fi
    local pid
    pid=$(cat "$pid_file")
    if kill -TERM "$pid" 2>/dev/null; then
        echo "  🛑 $name stopped (pid $pid)"
    else
        echo "  ⚠️  $name pid $pid already gone"
    fi
    rm -f "$pid_file"
}

status_bot() {
    local name="$1"
    local pid_file="$PID_DIR/${name}.pid"

    if [[ ! -f "$pid_file" ]]; then
        echo "  🔴 $name — not running"
        return
    fi
    local pid
    pid=$(cat "$pid_file")
    if kill -0 "$pid" 2>/dev/null; then
        echo "  🟢 $name — running (pid $pid)"
    else
        echo "  🔴 $name — dead (stale pid $pid)"
        rm -f "$pid_file"
    fi
}

# ── Commands ──────────────────────────────────────────────────────────────────

CMD="${1:-start}"

case "$CMD" in
    start)
        echo "🚀 Starting all ThreeWordsDaily bots..."
        for name in "${!BOTS[@]}"; do
            start_bot "$name" "${BOTS[$name]}"
        done
        echo ""
        echo "📋 Logs: $LOG_DIR/"
        echo "📌 Stop: bash run.sh stop"
        ;;

    stop)
        echo "🛑 Stopping all bots..."
        for name in "${!BOTS[@]}"; do
            stop_bot "$name"
        done
        ;;

    restart)
        echo "🔄 Restarting all bots..."
        for name in "${!BOTS[@]}"; do
            stop_bot "$name"
        done
        sleep 2
        for name in "${!BOTS[@]}"; do
            start_bot "$name" "${BOTS[$name]}"
        done
        ;;

    status)
        echo "📊 Bot status:"
        for name in "${!BOTS[@]}"; do
            status_bot "$name"
        done
        ;;

    logs)
        BOT="${2:-learning_bot}"
        LOG_FILE="$LOG_DIR/${BOT}.log"
        if [[ -f "$LOG_FILE" ]]; then
            tail -f "$LOG_FILE"
        else
            echo "No log file for $BOT at $LOG_FILE"
        fi
        ;;

    *)
        echo "Usage: bash run.sh [start|stop|restart|status|logs [bot_name]]"
        exit 1
        ;;
esac
