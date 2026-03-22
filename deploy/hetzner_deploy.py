"""
deploy/hetzner_deploy.py — Create VPS on Hetzner and deploy VoodooBot.

Usage:
    python3 deploy/hetzner_deploy.py              # Create + deploy
    python3 deploy/hetzner_deploy.py --status     # Check server status
    python3 deploy/hetzner_deploy.py --destroy    # Delete server (careful!)
    python3 deploy/hetzner_deploy.py --logs       # Stream logs from server
    python3 deploy/hetzner_deploy.py --redeploy   # Push latest code + restart bots
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

HETZNER_TOKEN = os.getenv("HETZNER_API_TOKEN", "")
HETZNER_API   = "https://api.hetzner.cloud/v1"
SERVER_NAME   = "voodoobot"
SERVER_TYPE   = "cx22"       # 2 vCPU, 4GB RAM, 40GB disk — €4.15/mo
LOCATION      = "nbg1"       # Nuremberg (EU, low Ukraine latency)
IMAGE         = "ubuntu-24.04"
DEPLOY_DIR    = "/opt/voodoo"
ENV_FILE      = Path(__file__).parent.parent / ".env"
STATE_FILE    = Path(__file__).parent / "hetzner_state.json"

# ── Startup script installed on the server ──────────────────────────────────
CLOUD_INIT = r"""#!/bin/bash
set -e
apt-get update -q
apt-get install -yq python3.12 python3.12-venv python3-pip git curl ufw screen sqlite3

# Firewall
ufw allow 22/tcp
ufw allow 9000/tcp
ufw --force enable

# Clone repo
git clone https://github.com/kapytt2020-jpg/ThreeWordsDaily /opt/voodoo
cd /opt/voodoo
git checkout voodoo

# Venv + deps
python3.12 -m venv venv
source venv/bin/activate
pip install -q -r requirements.txt

mkdir -p database logs

echo "VOODOO_CLOUD_INIT_DONE=1" >> /opt/voodoo/.env
"""


def headers() -> dict:
    return {"Authorization": f"Bearer {HETZNER_TOKEN}", "Content-Type": "application/json"}


def api(method: str, path: str, **kwargs):
    resp = requests.request(method, f"{HETZNER_API}/{path}", headers=headers(), **kwargs)
    if resp.status_code >= 400:
        raise RuntimeError(f"Hetzner API {method} /{path} → {resp.status_code}: {resp.text[:300]}")
    return resp.json() if resp.content else {}


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(data: dict):
    STATE_FILE.write_text(json.dumps(data, indent=2))


def get_server_id() -> int | None:
    state = load_state()
    return state.get("server_id")


def create_ssh_key() -> int:
    """Upload local ~/.ssh/id_rsa.pub or generate a new keypair."""
    pub_key_paths = [
        Path.home() / ".ssh/id_ed25519.pub",
        Path.home() / ".ssh/id_rsa.pub",
    ]
    pub_key = None
    for p in pub_key_paths:
        if p.exists():
            pub_key = p.read_text().strip()
            print(f"  Using SSH key: {p}")
            break

    if not pub_key:
        print("  Generating new SSH keypair...")
        key_path = Path.home() / ".ssh/voodoo_deploy"
        subprocess.run(["ssh-keygen", "-t", "ed25519", "-f", str(key_path), "-N", "", "-C", "voodoobot-deploy"], check=True)
        pub_key = (key_path.with_suffix(".pub")).read_text().strip()
        print(f"  New key: {key_path}")

    # Check if key already exists
    existing = api("GET", "ssh_keys")
    for k in existing.get("ssh_keys", []):
        if k["public_key"].strip() == pub_key.split(" ")[0] + " " + pub_key.split(" ")[1]:
            print(f"  SSH key already in Hetzner: {k['name']} (id={k['id']})")
            return k["id"]

    result = api("POST", "ssh_keys", json={"name": "voodoobot-key", "public_key": pub_key})
    key_id = result["ssh_key"]["id"]
    print(f"  SSH key uploaded (id={key_id})")
    return key_id


def create_server(key_id: int) -> dict:
    print(f"\n🚀 Creating Hetzner server '{SERVER_NAME}' ({SERVER_TYPE}, {LOCATION})...")
    result = api("POST", "servers", json={
        "name": SERVER_NAME,
        "server_type": SERVER_TYPE,
        "location": LOCATION,
        "image": IMAGE,
        "ssh_keys": [key_id],
        "user_data": CLOUD_INIT,
        "labels": {"project": "voodoobot"},
    })
    server = result["server"]
    root_pw = result.get("root_password", "(use SSH key)")
    return server, root_pw


def wait_for_server(server_id: int, timeout: int = 120) -> str:
    """Poll until server is running. Returns IPv4."""
    print("⏳ Waiting for server to start", end="", flush=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        info = api("GET", f"servers/{server_id}")["server"]
        if info["status"] == "running":
            ip = info["public_net"]["ipv4"]["ip"]
            print(f" ✅ Running! IP: {ip}")
            return ip
        print(".", end="", flush=True)
        time.sleep(5)
    raise TimeoutError("Server did not start in time")


def copy_env(ip: str):
    """SCP .env to server."""
    print(f"\n📦 Uploading .env to {ip}...")
    # Remove local-only values that don't apply to server
    env_content = ENV_FILE.read_text()
    # Remove DB_PATH override (server uses /opt/voodoo/database/voodoo.db)
    env_content = re.sub(r"^DB_PATH=.*$", "DB_PATH=/opt/voodoo/database/voodoo.db", env_content, flags=re.MULTILINE)
    # Write temp .env
    tmp_env = Path("/tmp/voodoo_server.env")
    tmp_env.write_text(env_content)

    for attempt in range(8):
        result = subprocess.run([
            "scp", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10",
            str(tmp_env), f"root@{ip}:{DEPLOY_DIR}/.env"
        ], capture_output=True, text=True)
        if result.returncode == 0:
            print("  ✅ .env uploaded")
            tmp_env.unlink(missing_ok=True)
            return
        print(f"  Retry {attempt+1}/8 (server still booting)...")
        time.sleep(15)
    raise RuntimeError("Could not copy .env to server: " + result.stderr)


def run_remote(ip: str, cmd: str, check: bool = True) -> str:
    result = subprocess.run(
        ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=15",
         f"root@{ip}", cmd],
        capture_output=True, text=True
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"Remote cmd failed: {result.stderr[:200]}")
    return result.stdout + result.stderr


def wait_for_cloud_init(ip: str, timeout: int = 300):
    """Wait until cloud-init (apt installs + git clone) finishes."""
    print("⏳ Waiting for cloud-init to finish (git clone + pip install)...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        out = run_remote(ip, "test -f /opt/voodoo/.env && echo DONE || echo WAIT", check=False)
        if "DONE" in out:
            print("  ✅ Cloud-init done")
            return
        print(".", end="", flush=True)
        time.sleep(20)
    print("\n  ⚠️  Cloud-init timeout — continuing anyway")


def install_systemd_services(ip: str):
    print("\n⚙️  Installing systemd services...")
    run_remote(ip, "bash /opt/voodoo/deploy/setup_server.sh 2>&1 | tail -20")
    print("  ✅ Services installed")


def start_all_bots(ip: str):
    print("\n🤖 Starting all bots...")
    bots = [
        "voodoo_bot", "voodoo_speak_bot", "voodoo_teacher_bot",
        "voodoo_publisher_bot", "voodoo_analyst_bot", "voodoo_growth_bot",
        "voodoo_ops_bot", "voodoo_group_manager", "voodoo_content_scheduler",
    ]
    run_remote(ip, f"systemctl enable {' '.join(bots)}")
    run_remote(ip, f"systemctl start {' '.join(bots)}")
    print("  ✅ All bots started")


def print_status(ip: str):
    print(f"\n📊 Bot status on {ip}:")
    out = run_remote(ip, "systemctl is-active voodoo_bot voodoo_speak_bot voodoo_teacher_bot voodoo_publisher_bot voodoo_analyst_bot voodoo_group_manager voodoo_content_scheduler 2>&1", check=False)
    print(out)


# ── CLI entry points ─────────────────────────────────────────────────────────

def cmd_create():
    if not HETZNER_TOKEN:
        print("❌ HETZNER_API_TOKEN not set in .env")
        print("   Get it: console.hetzner.cloud → Security → API Tokens")
        sys.exit(1)

    state = load_state()
    if state.get("server_id"):
        print(f"ℹ️  Server already exists (id={state['server_id']}, ip={state.get('ip')})")
        print("   Use --redeploy to push new code, or --destroy to remove")
        return

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  VoodooBot → Hetzner Deploy")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    key_id = create_ssh_key()
    server, root_pw = create_server(key_id)
    server_id = server["id"]
    save_state({"server_id": server_id, "name": SERVER_NAME})
    print(f"  Server ID: {server_id}")

    ip = wait_for_server(server_id)
    save_state({"server_id": server_id, "name": SERVER_NAME, "ip": ip})

    # Wait for SSH to be available
    print("\n⏳ Waiting for SSH...", end="", flush=True)
    for _ in range(20):
        r = subprocess.run(["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
                            f"root@{ip}", "echo ok"], capture_output=True)
        if r.returncode == 0:
            print(" ✅")
            break
        print(".", end="", flush=True)
        time.sleep(5)

    copy_env(ip)
    wait_for_cloud_init(ip)
    install_systemd_services(ip)
    start_all_bots(ip)
    print_status(ip)

    print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✅ VoodooBot deployed!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Server IP:   {ip}
  SSH:         ssh root@{ip}
  Logs:        ssh root@{ip} 'tail -f /opt/voodoo/logs/voodoo_bot.log'
  Status:      python3 deploy/hetzner_deploy.py --status
  Redeploy:    python3 deploy/hetzner_deploy.py --redeploy
  Cost:        ~€4/month
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")


def cmd_status():
    state = load_state()
    ip = state.get("ip")
    if not ip:
        print("❌ No server found. Run without flags to create one.")
        return
    print(f"Server: {state.get('name')} ({ip})")
    print_status(ip)


def cmd_destroy():
    state = load_state()
    sid = state.get("server_id")
    if not sid:
        print("No server to destroy")
        return
    confirm = input(f"Delete server {state.get('name')} (id={sid})? This cannot be undone. [yes/N]: ").strip()
    if confirm.lower() != "yes":
        print("Cancelled")
        return
    api("DELETE", f"servers/{sid}")
    STATE_FILE.unlink(missing_ok=True)
    print("✅ Server deleted")


def cmd_redeploy():
    state = load_state()
    ip = state.get("ip")
    if not ip:
        print("❌ No server. Run without flags first.")
        return
    print(f"🔄 Redeploying to {ip}...")
    copy_env(ip)
    run_remote(ip, "cd /opt/voodoo && git pull origin voodoo")
    run_remote(ip, "cd /opt/voodoo && source venv/bin/activate && pip install -q -r requirements.txt")
    bots = ["voodoo_bot", "voodoo_speak_bot", "voodoo_teacher_bot", "voodoo_publisher_bot",
            "voodoo_analyst_bot", "voodoo_growth_bot", "voodoo_ops_bot",
            "voodoo_group_manager", "voodoo_content_scheduler"]
    run_remote(ip, f"systemctl restart {' '.join(bots)}")
    print("✅ Redeployed and restarted")
    print_status(ip)


def cmd_logs():
    state = load_state()
    ip = state.get("ip")
    if not ip:
        print("❌ No server found.")
        return
    bot = sys.argv[2] if len(sys.argv) > 2 else "voodoo_bot"
    print(f"Streaming logs for {bot} from {ip}... (Ctrl+C to stop)")
    subprocess.run(["ssh", "-o", "StrictHostKeyChecking=no", f"root@{ip}",
                    f"tail -f /opt/voodoo/logs/{bot}.log"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hetzner VPS deploy for VoodooBot")
    parser.add_argument("--status",   action="store_true")
    parser.add_argument("--destroy",  action="store_true")
    parser.add_argument("--redeploy", action="store_true")
    parser.add_argument("--logs",     action="store_true")
    args = parser.parse_args()

    if args.status:
        cmd_status()
    elif args.destroy:
        cmd_destroy()
    elif args.redeploy:
        cmd_redeploy()
    elif args.logs:
        cmd_logs()
    else:
        cmd_create()
