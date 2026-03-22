#!/bin/bash
# deploy/tunnel_watchdog.sh
# Monitors cloudflared quick tunnel URL, updates .env + restarts voodoo_bot when URL changes.
# Run as systemd service: voodoo_tunnel_watchdog

ENV_FILE="/opt/voodoo/.env"
LOG_FILE="/opt/voodoo/logs/cloudflared.log"
LAST_URL=""

while true; do
  # Extract latest tunnel URL from log
  CURRENT_URL=$(grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG_FILE" 2>/dev/null | tail -1)

  if [[ -n "$CURRENT_URL" && "$CURRENT_URL" != "$LAST_URL" ]]; then
    echo "[tunnel_watchdog] New URL: $CURRENT_URL"
    sed -i "s|MINIAPP_URL=.*|MINIAPP_URL=$CURRENT_URL|" "$ENV_FILE"
    systemctl restart voodoo_bot
    LAST_URL="$CURRENT_URL"
    echo "[tunnel_watchdog] voodoo_bot restarted with new MINIAPP_URL"
  fi

  sleep 15
done
