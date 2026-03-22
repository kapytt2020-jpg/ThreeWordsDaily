"""
deploy/vultr_deploy.py — Create VPS on Vultr and deploy VoodooBot.

Usage:
    python3 deploy/vultr_deploy.py              # Create + deploy
    python3 deploy/vultr_deploy.py --status     # Check server status
    python3 deploy/vultr_deploy.py --destroy    # Delete server
    python3 deploy/vultr_deploy.py --redeploy   # Push latest code + restart bots
    python3 deploy/vultr_deploy.py --logs       # Stream logs from server
"""

from __future__ import annotations

import argparse
import base64
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

VULTR_TOKEN  = os.getenv("VULTR_API_KEY", "")
API_BASE     = "https://api.vultr.com/v2"
LABEL        = "voodoobot"
PLAN         = "vc2-1c-2gb"   # 1 vCPU, 2GB RAM, 55GB — $10/mo (bots need ~800MB)
REGION       = "fra"           # Frankfurt — best latency for Ukraine
OS_ID        = 2284            # Ubuntu 24.04 LTS
DEPLOY_DIR   = "/opt/voodoo"
STATE_FILE   = Path(__file__).parent / "vultr_state.json"
ENV_FILE     = Path(__file__).parent.parent / ".env"

STARTUP_SCRIPT = r"""#!/bin/bash
set -e
export DEBIAN_FRONTEND=noninteractive

apt-get update -qq
apt-get install -yq python3.12 python3.12-venv python3-pip git curl ufw screen sqlite3 ffmpeg

# Firewall — only SSH + group manager API
ufw allow 22/tcp
ufw allow 9000/tcp
ufw --force enable

# Clone VoodooBot
git clone https://github.com/kapytt2020-jpg/ThreeWordsDaily /opt/voodoo
cd /opt/voodoo
git checkout voodoo

# Python venv + deps
python3.12 -m venv venv
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Directories
mkdir -p /opt/voodoo/{database,logs}

# Signal that cloud-init is done
touch /opt/voodoo/.cloud_init_done
"""


def headers() -> dict:
    return {"Authorization": f"Bearer {VULTR_TOKEN}", "Content-Type": "application/json"}


def api(method: str, path: str, **kwargs) -> dict:
    resp = requests.request(method, f"{API_BASE}/{path}", headers=headers(), **kwargs)
    if resp.status_code == 204:
        return {}
    if resp.status_code >= 400:
        raise RuntimeError(f"Vultr {method} {path} → {resp.status_code}: {resp.text[:300]}")
    return resp.json() if resp.content else {}


def load_state() -> dict:
    return json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}


def save_state(data: dict):
    STATE_FILE.write_text(json.dumps(data, indent=2))


def get_or_create_ssh_key() -> str:
    """Upload SSH pub key to Vultr, return key ID."""
    kp = Path.home() / ".ssh/voodoo_deploy"

    # Use or generate dedicated deploy key (never overwrite existing)
    if not kp.exists():
        print("  Generating SSH keypair...")
        subprocess.run(
            ["ssh-keygen", "-t", "ed25519", "-f", str(kp), "-N", "", "-C", "voodoobot"],
            check=True, capture_output=True
        )

    pub_key = kp.with_suffix(".pub").read_text().strip()
    print(f"  Using SSH key: {kp.name}")

    # Compare full public key body (not just prefix) with Vultr stored keys
    pub_body = pub_key.split()[1]  # base64 key material
    existing = api("GET", "ssh-keys").get("ssh_keys", [])
    for k in existing:
        stored_body = k.get("ssh_key", "").split()[1] if len(k.get("ssh_key", "").split()) > 1 else ""
        if stored_body == pub_body:
            print(f"  SSH key already in Vultr: {k['name']}")
            return k["id"]

    result = api("POST", "ssh-keys", json={"name": "voodoobot-key", "ssh_key": pub_key})
    kid = result["ssh_key"]["id"]
    print(f"  SSH key uploaded (id={kid})")
    return kid


def create_startup_script() -> str:
    """Upload startup script to Vultr, return script ID."""
    existing = api("GET", "startup-scripts").get("startup_scripts", [])
    for s in existing:
        if s["name"] == "voodoobot-init":
            encoded = base64.b64encode(STARTUP_SCRIPT.encode()).decode()
            api("PATCH", f"startup-scripts/{s['id']}", json={"script": encoded})
            print(f"  Startup script updated (id={s['id']})")
            return s["id"]

    encoded = base64.b64encode(STARTUP_SCRIPT.encode()).decode()
    result = api("POST", "startup-scripts", json={
        "name": "voodoobot-init",
        "type": "boot",
        "script": encoded,
    })
    sid = result["startup_script"]["id"]
    print(f"  Startup script created (id={sid})")
    return sid


def create_instance(ssh_key_id: str, script_id: str) -> dict:
    print(f"\n🚀 Creating Vultr instance '{LABEL}' ({PLAN}, {REGION})...")
    result = api("POST", "instances", json={
        "label": LABEL,
        "region": REGION,
        "plan": PLAN,
        "os_id": OS_ID,
        "sshkey_id": [ssh_key_id],
        "script_id": script_id,
        "hostname": LABEL,
        "enable_ipv6": False,
        "tags": ["voodoobot"],
    })
    return result["instance"]


def wait_for_running(instance_id: str, timeout: int = 180) -> str:
    """Poll until instance is active. Returns IPv4."""
    print("⏳ Booting", end="", flush=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        info = api("GET", f"instances/{instance_id}")["instance"]
        if info["status"] == "active" and info["main_ip"] and info["main_ip"] != "0.0.0.0":
            ip = info["main_ip"]
            print(f" ✅ Active! IP: {ip}")
            return ip
        print(".", end="", flush=True)
        time.sleep(8)
    raise TimeoutError("Instance did not become active in time")


def wait_for_ssh(ip: str, timeout: int = 180):
    print("⏳ Waiting for SSH", end="", flush=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=6",
             f"root@{ip}", "echo ok"],
            capture_output=True
        )
        if r.returncode == 0:
            print(" ✅")
            return
        print(".", end="", flush=True)
        time.sleep(8)
    raise TimeoutError("SSH not available")


def run_remote(ip: str, cmd: str, check: bool = True) -> str:
    ssh_key = Path.home() / ".ssh/voodoo_deploy"
    key_args = ["-i", str(ssh_key)] if ssh_key.exists() else []
    r = subprocess.run(
        ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=20"]
        + key_args + [f"root@{ip}", cmd],
        capture_output=True, text=True
    )
    if check and r.returncode != 0:
        raise RuntimeError(f"Remote failed ({r.returncode}): {r.stderr[:300]}")
    return r.stdout + r.stderr


def copy_env(ip: str):
    print(f"\n📦 Uploading .env...")
    env_content = ENV_FILE.read_text()
    env_content = re.sub(r"^DB_PATH=.*$", f"DB_PATH={DEPLOY_DIR}/database/voodoo.db",
                         env_content, flags=re.MULTILINE)
    tmp = Path("/tmp/voodoo_server.env")
    tmp.write_text(env_content)

    ssh_key = Path.home() / ".ssh/voodoo_deploy"
    key_args = ["-i", str(ssh_key)] if ssh_key.exists() else []

    for attempt in range(10):
        r = subprocess.run(
            ["scp", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10"]
            + key_args
            + [str(tmp), f"root@{ip}:{DEPLOY_DIR}/.env"],
            capture_output=True, text=True
        )
        if r.returncode == 0:
            print("  ✅ .env uploaded")
            tmp.unlink(missing_ok=True)
            return
        time.sleep(12)
    raise RuntimeError("Could not scp .env: " + r.stderr)


def wait_cloud_init(ip: str, timeout: int = 600):
    print("⏳ Waiting for cloud-init (apt + pip install, ~3-5 min)...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        out = run_remote(ip, "test -f /opt/voodoo/.cloud_init_done && echo DONE || echo WAIT", check=False)
        if "DONE" in out:
            print("  ✅ Ready")
            return
        time.sleep(20)
        print(".", end="", flush=True)
    print("\n  ⚠️  Timeout — continuing anyway")


def install_services(ip: str):
    print("\n⚙️  Installing systemd services...")
    # Run setup_server.sh but skip the parts we've already done
    run_remote(ip, f"bash {DEPLOY_DIR}/deploy/setup_server.sh 2>&1 | tail -5")
    print("  ✅ Done")


def start_bots(ip: str):
    print("\n🤖 Starting all bots...")
    bots = [
        "voodoo_bot", "voodoo_speak_bot", "voodoo_teacher_bot",
        "voodoo_publisher_bot", "voodoo_analyst_bot", "voodoo_growth_bot",
        "voodoo_ops_bot", "voodoo_group_manager", "voodoo_content_scheduler",
    ]
    run_remote(ip, f"systemctl enable {' '.join(bots)} 2>/dev/null; systemctl start {' '.join(bots)}")
    print("  ✅ Started")


def print_status(ip: str):
    print(f"\n📊 Status on {ip}:")
    out = run_remote(ip,
        "systemctl is-active voodoo_bot voodoo_speak_bot voodoo_teacher_bot "
        "voodoo_publisher_bot voodoo_analyst_bot voodoo_group_manager voodoo_content_scheduler",
        check=False
    )
    services = ["voodoo_bot", "speak", "teacher", "publisher", "analyst", "group_manager", "scheduler"]
    for name, status in zip(services, out.strip().splitlines()):
        icon = "✅" if status == "active" else "❌"
        print(f"  {icon} {name}: {status}")


# ── Commands ─────────────────────────────────────────────────────────────────

def cmd_create():
    if not VULTR_TOKEN:
        print("❌ VULTR_API_KEY not set in .env")
        sys.exit(1)

    state = load_state()
    if state.get("instance_id"):
        print(f"ℹ️  Instance exists (id={state['instance_id']}, ip={state.get('ip')})")
        print("   --redeploy to push code, --destroy to remove")
        return

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  VoodooBot → Vultr Deploy")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    ssh_key_id = get_or_create_ssh_key()
    script_id  = create_startup_script()
    instance   = create_instance(ssh_key_id, script_id)
    iid        = instance["id"]

    save_state({"instance_id": iid, "label": LABEL})
    ip = wait_for_running(iid)
    save_state({"instance_id": iid, "label": LABEL, "ip": ip})

    wait_for_ssh(ip)
    copy_env(ip)
    wait_cloud_init(ip)
    install_services(ip)
    start_bots(ip)
    print_status(ip)

    print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✅ VoodooBot is LIVE on Vultr!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IP:       {ip}
  SSH:      ssh root@{ip}
  Logs:     python3 deploy/vultr_deploy.py --logs
  Status:   python3 deploy/vultr_deploy.py --status
  Redeploy: python3 deploy/vultr_deploy.py --redeploy
  Cost:     ~$10/month
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")


def cmd_status():
    state = load_state()
    ip = state.get("ip")
    if not ip:
        print("❌ No server. Run without flags to create.")
        return
    print(f"Instance: {state.get('label')} | {state.get('instance_id')} | {ip}")
    print_status(ip)


def cmd_destroy():
    state = load_state()
    iid = state.get("instance_id")
    if not iid:
        print("No instance to destroy")
        return
    confirm = input(f"Delete instance {state.get('label')} ({iid})? [yes/N]: ").strip()
    if confirm.lower() != "yes":
        print("Cancelled")
        return
    api("DELETE", f"instances/{iid}")
    STATE_FILE.unlink(missing_ok=True)
    print("✅ Instance deleted")


def cmd_redeploy():
    state = load_state()
    ip = state.get("ip")
    if not ip:
        print("❌ No instance. Run without flags first.")
        return
    print(f"🔄 Redeploying to {ip}...")
    copy_env(ip)
    run_remote(ip, f"cd {DEPLOY_DIR} && git pull origin voodoo")
    run_remote(ip, f"cd {DEPLOY_DIR} && source venv/bin/activate && pip install -q -r requirements.txt")
    bots = ["voodoo_bot", "voodoo_speak_bot", "voodoo_teacher_bot", "voodoo_publisher_bot",
            "voodoo_analyst_bot", "voodoo_growth_bot", "voodoo_ops_bot",
            "voodoo_group_manager", "voodoo_content_scheduler"]
    run_remote(ip, f"systemctl restart {' '.join(bots)}")
    print("✅ Redeployed!")
    print_status(ip)


def cmd_logs(bot: str = "voodoo_bot"):
    state = load_state()
    ip = state.get("ip")
    if not ip:
        print("❌ No server.")
        return
    print(f"📋 {bot} logs (Ctrl+C to stop):")
    subprocess.run(["ssh", "-o", "StrictHostKeyChecking=no", f"root@{ip}",
                    f"journalctl -u {bot} -f --no-pager"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--status",   action="store_true")
    parser.add_argument("--destroy",  action="store_true")
    parser.add_argument("--redeploy", action="store_true")
    parser.add_argument("--logs",     nargs="?", const="voodoo_bot", metavar="BOT")
    args = parser.parse_args()

    if args.status:
        cmd_status()
    elif args.destroy:
        cmd_destroy()
    elif args.redeploy:
        cmd_redeploy()
    elif args.logs is not None:
        cmd_logs(args.logs)
    else:
        cmd_create()
