"""
watchdog.py — Voodoo Platform Health Monitor

Checks all services every 5 minutes.
Sends Telegram alert + attempts auto-restart if a service is down.
Run via LaunchAgent: com.voodoo.watchdog
"""

import asyncio
import json
import logging
import os
import subprocess
import urllib.request
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format="%(asctime)s [watchdog] %(levelname)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("watchdog")

OPS_BOT_TOKEN = os.getenv("VOODOO_OPS_BOT_TOKEN", "")
ADMIN_CHAT_ID  = int(os.getenv("ADMIN_CHAT_ID", "0"))

SERVICES = {
    "voodoo_bot":       ("com.voodoo.bot",          "voodoo_bot.py"),
    "speak_bot":        ("com.voodoo.speak_bot",     "voodoo_speak_bot.py"),
    "teacher_bot":      ("com.voodoo.teacher_bot",   "voodoo_teacher_bot.py"),
    "publisher_bot":    ("com.voodoo.publisher_bot", "voodoo_publisher_bot.py"),
    "analyst_bot":      ("com.voodoo.analyst_bot",   "voodoo_analyst_bot.py"),
    "growth_bot":       ("com.voodoo.growth_bot",    "voodoo_growth_bot.py"),
    "ops_bot":          ("com.voodoo.ops_bot",       "voodoo_ops_bot.py"),
    "test_bot":         ("com.voodoo.test_bot",      "voodoo_test_bot.py"),
    "miniapp":          ("com.voodoo.miniapp",       "uvicorn"),
}


def is_running(keyword: str) -> bool:
    r = subprocess.run(["pgrep", "-f", keyword], capture_output=True)
    return r.returncode == 0


def restart_service(label: str, name: str = "") -> bool:
    try:
        if name == "miniapp":
            # Free port 8000 first
            r = subprocess.run(["lsof", "-ti", ":8000"], capture_output=True, text=True)
            for pid in r.stdout.strip().split():
                if pid.isdigit():
                    subprocess.run(["kill", "-9", pid], capture_output=True)
            import time; time.sleep(1)
        subprocess.run(
            ["/bin/launchctl", "kickstart", "-k", f"gui/{os.getuid()}/{label}"],
            capture_output=True, timeout=15,
        )
        return True
    except Exception as exc:
        log.error("restart_service(%s) failed: %s", label, exc)
        return False


def send_alert(text: str) -> None:
    if not OPS_BOT_TOKEN or not ADMIN_CHAT_ID:
        log.warning("OPS_BOT_TOKEN or ADMIN_CHAT_ID not set")
        return
    try:
        payload = json.dumps({
            "chat_id": ADMIN_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
        }).encode()
        url = f"https://api.telegram.org/bot{OPS_BOT_TOKEN}/sendMessage"
        req = urllib.request.Request(
            url, data=payload, headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=10)
        log.info("Alert sent")
    except Exception as exc:
        log.error("send_alert failed: %s", exc)


def check_all() -> None:
    down, restarted = [], []

    for name, (label, keyword) in SERVICES.items():
        if not is_running(keyword):
            down.append(name)
            log.warning("⚠️ %s DOWN — restarting...", name)
            if restart_service(label, name):
                restarted.append(name)

    if down:
        now   = datetime.now().strftime("%d.%m %H:%M")
        dlist = "\n".join(f"  💀 {s}" for s in down)
        rlist = "\n".join(f"  ↻ {s}" for s in restarted) if restarted else "  ❌ failed"
        send_alert(
            f"⚠️ <b>Voodoo Watchdog — {now}</b>\n\n"
            f"<b>Down:</b>\n{dlist}\n\n"
            f"<b>Restarted:</b>\n{rlist}\n\n"
            f"<code>tail -50 ~/Desktop/VoodooBot/logs/*.log</code>"
        )
    else:
        log.info("✅ All %d services OK", len(SERVICES))


if __name__ == "__main__":
    log.info("Voodoo Watchdog started — monitoring %d services", len(SERVICES))
    check_all()
