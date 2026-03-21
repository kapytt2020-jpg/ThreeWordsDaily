#!/bin/bash
# ThreeWordsDaily — VPS Setup Script
# Run once on a fresh Ubuntu 22.04 server:
#   curl -fsSL https://raw.githubusercontent.com/YOUR/REPO/main/deploy/setup_vps.sh | bash
#
# Or manually: bash setup_vps.sh

set -e

echo "=== ThreeWordsDaily VPS Setup ==="

# 1. Install Docker
if ! command -v docker &>/dev/null; then
  echo "[1/5] Installing Docker..."
  curl -fsSL https://get.docker.com | sh
  usermod -aG docker $USER
  echo "Docker installed."
else
  echo "[1/5] Docker already installed."
fi

# 2. Install Docker Compose
if ! command -v docker &>/dev/null || ! docker compose version &>/dev/null; then
  echo "[2/5] Installing Docker Compose plugin..."
  apt-get update -q && apt-get install -y docker-compose-plugin
else
  echo "[2/5] Docker Compose already installed."
fi

# 3. Clone or pull repo
PROJECT_DIR="/opt/threewordsdaily"
if [ -d "$PROJECT_DIR/.git" ]; then
  echo "[3/5] Pulling latest code..."
  cd "$PROJECT_DIR" && git pull
else
  echo "[3/5] Cloning project..."
  echo "  Enter your GitHub repo URL (or press Enter to skip and copy files manually):"
  read REPO_URL
  if [ -n "$REPO_URL" ]; then
    git clone "$REPO_URL" "$PROJECT_DIR"
  else
    mkdir -p "$PROJECT_DIR"
    echo "  → Copy project files to $PROJECT_DIR manually, then run: cd $PROJECT_DIR && bash deploy/start.sh"
    exit 0
  fi
fi

cd "$PROJECT_DIR"

# 4. Create .env if missing
if [ ! -f ".env" ]; then
  echo "[4/5] Creating .env from template..."
  cp .env.example .env
  echo ""
  echo "  ⚠️  Fill in your tokens in $PROJECT_DIR/.env"
  echo "  Then run: cd $PROJECT_DIR && bash deploy/start.sh"
  exit 0
else
  echo "[4/5] .env already exists."
fi

# 5. Start everything
echo "[5/5] Starting all services..."
docker compose pull --ignore-pull-failures 2>/dev/null || true
docker compose up -d --build

echo ""
echo "✅ Done! All bots running autonomously."
echo ""
echo "Useful commands:"
echo "  docker compose ps           — status"
echo "  docker compose logs -f      — live logs"
echo "  docker compose restart      — restart all"
echo "  docker compose down         — stop all"
