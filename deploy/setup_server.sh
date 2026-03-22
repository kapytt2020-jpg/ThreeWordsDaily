#!/bin/bash
# ============================================================
# VoodooBot — Server Setup Script
# Tested on Ubuntu 22.04 / 24.04 (Oracle Cloud, Hetzner, DO)
# Run as root or with sudo:
#   curl -sL [url] | bash
#   OR: bash setup_server.sh
# ============================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }

# ── 1. System update ──────────────────────────────────────
log "Updating system packages..."
apt-get update -q && apt-get upgrade -yq

# ── 2. Python 3.11+ ───────────────────────────────────────
log "Installing Python 3.11..."
apt-get install -yq python3.11 python3.11-venv python3-pip python3.11-dev
update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# ── 3. System tools ───────────────────────────────────────
log "Installing system tools..."
apt-get install -yq git curl wget ffmpeg sqlite3 screen htop lsof ufw

# ── 4. Firewall ───────────────────────────────────────────
log "Configuring firewall..."
ufw allow 22/tcp   # SSH
ufw allow 9000/tcp # Group Manager API (localhost only normally, but allow for debug)
ufw --force enable

# ── 5. Clone VoodooBot ────────────────────────────────────
INSTALL_DIR="/opt/voodoo"
if [ -d "$INSTALL_DIR" ]; then
    warn "Directory $INSTALL_DIR exists. Pulling latest..."
    cd "$INSTALL_DIR" && git pull
else
    log "Cloning VoodooBot..."
    git clone https://github.com/kapytt2020-jpg/VoodooBot "$INSTALL_DIR" 2>/dev/null || {
        warn "GitHub clone failed — copying from current directory if available"
        mkdir -p "$INSTALL_DIR"
        cp -r . "$INSTALL_DIR/" 2>/dev/null || true
    }
fi

cd "$INSTALL_DIR"

# ── 6. Python venv + deps ─────────────────────────────────
log "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

log "Installing Python dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

# ── 7. Database directories ───────────────────────────────
log "Setting up directories..."
mkdir -p database logs

# ── 8. .env check ─────────────────────────────────────────
if [ ! -f ".env" ]; then
    warn ".env not found — creating template..."
    cat > .env << 'ENVEOF'
VOODOO_BOT_TOKEN=
VOODOO_SPEAK_BOT_TOKEN=
VOODOO_TEACHER_BOT_TOKEN=
VOODOO_PUBLISHER_BOT_TOKEN=
VOODOO_ANALYST_BOT_TOKEN=
VOODOO_GROWTH_BOT_TOKEN=
VOODOO_OPS_BOT_TOKEN=
ADMIN_CHAT_ID=
INTERNAL_GROUP_ID=
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
DB_PATH=/opt/voodoo/database/voodoo.db
TELETHON_API_ID=
TELETHON_API_HASH=
TELETHON_SESSION=voodoo_manager
PODCAST_TOPIC_ID=76
HETZNER_API_TOKEN=
DO_API_TOKEN=
VULTR_API_KEY=
ENVEOF
    warn "Edit /opt/voodoo/.env with your tokens before starting!"
fi

# ── 9. systemd services ───────────────────────────────────
log "Installing systemd services..."

BOTS=(
    "voodoo_bot:bots/voodoo_bot.py"
    "voodoo_speak_bot:bots/voodoo_speak_bot.py"
    "voodoo_teacher_bot:bots/voodoo_teacher_bot.py"
    "voodoo_publisher_bot:bots/voodoo_publisher_bot.py"
    "voodoo_analyst_bot:bots/voodoo_analyst_bot.py"
    "voodoo_growth_bot:bots/voodoo_growth_bot.py"
    "voodoo_ops_bot:bots/voodoo_ops_bot.py"
    "voodoo_promo_bot:bots/voodoo_promo_bot.py"
    "voodoo_group_manager:group_manager.py"
    "voodoo_content_scheduler:agents/content_scheduler.py"
    "voodoo_autonomous_loop:agents/autonomous_loop.py"
    "voodoo_outreach_agent:agents/outreach_agent.py"
)

for entry in "${BOTS[@]}"; do
    NAME="${entry%%:*}"
    SCRIPT="${entry##*:}"

    cat > "/etc/systemd/system/${NAME}.service" << SVCEOF
[Unit]
Description=VoodooBot — ${NAME}
After=network.target
StartLimitIntervalSec=120
StartLimitBurst=5

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=${INSTALL_DIR}/.env
ExecStart=${INSTALL_DIR}/venv/bin/python3 ${INSTALL_DIR}/${SCRIPT}
Restart=on-failure
RestartSec=30
StandardOutput=append:${INSTALL_DIR}/logs/${NAME}.log
StandardError=append:${INSTALL_DIR}/logs/${NAME}_error.log

[Install]
WantedBy=multi-user.target
SVCEOF

done

# Fix outreach agent to run in daemon mode
sed -i "s|python3 ${INSTALL_DIR}/agents/outreach_agent.py$|python3 ${INSTALL_DIR}/agents/outreach_agent.py --daemon|" \
    /etc/systemd/system/voodoo_outreach_agent.service

systemctl daemon-reload
log "systemd services installed."

# ── 10. Print next steps ──────────────────────────────────
echo ""
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo -e "${GREEN}  VoodooBot Setup Complete!${NC}"
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo ""
echo "Next steps:"
echo "  1. Edit tokens:    nano /opt/voodoo/.env"
echo "  2. Start all bots: systemctl start voodoo_bot voodoo_speak_bot voodoo_teacher_bot"
echo "                     systemctl start voodoo_publisher_bot voodoo_analyst_bot"
echo "                     systemctl start voodoo_growth_bot voodoo_ops_bot voodoo_promo_bot"
echo "                     systemctl start voodoo_group_manager voodoo_content_scheduler"
echo "                     systemctl start voodoo_autonomous_loop voodoo_outreach_agent"
echo "  3. Enable on boot: systemctl enable voodoo_bot voodoo_speak_bot ..."
echo "  3b. Scale markets: python3 agents/scaling_manager.py --market ru"
echo "  3c. Outreach now:  python3 agents/outreach_agent.py --run"
echo "  4. Check status:   systemctl status voodoo_bot"
echo "  5. View logs:      tail -f /opt/voodoo/logs/voodoo_bot.log"
echo ""
