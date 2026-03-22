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
    voodoo_promo_bot
)

start_service() {
    local name="$1"
    local cmd="$2"
    echo "▶ Starting $name..."
    eval "nohup $cmd >> $LOG_DIR/${name}.log 2>&1 &"
    echo "$!" > "$LOG_DIR/${name}.pid"
    echo "✅ $name started (PID $!)"
}

case "${1:-all}" in
    all)
        # Start all bots
        for bot in "${BOTS[@]}"; do
            start_bot "$bot"
        done

        # Start miniapp
        start_service "miniapp" "cd miniapp && $PYTHON -m uvicorn voodoo_api:app --host 0.0.0.0 --port 8000"

        # Start group_manager
        start_service "group_manager" "$PYTHON group_manager.py"

        # Start autonomous_loop
        start_service "autonomous_loop" "$PYTHON agents/autonomous_loop.py"

        # Start cloudflared tunnel for miniapp
        echo "▶ Starting cloudflare tunnel..."
        nohup cloudflared tunnel --url http://localhost:8000 >> "$LOG_DIR/cloudflared.log" 2>&1 &
        sleep 6
        TUNNEL_URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$LOG_DIR/cloudflared.log" | tail -1)
        if [ -n "$TUNNEL_URL" ]; then
            sed -i '' "s|MINIAPP_URL=.*|MINIAPP_URL=$TUNNEL_URL|" .env
            echo "🌐 MiniApp URL: $TUNNEL_URL"
        fi

        echo ""
        echo "✅ Voodoo Platform запущено"
        echo "📱 MiniApp: $TUNNEL_URL"
        echo "📊 Group API: http://127.0.0.1:9000/status"
        echo "📁 Logs: $LOG_DIR/"
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
