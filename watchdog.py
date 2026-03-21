"""
watchdog.py — Bot Health Monitor

Checks every 5 minutes that all 7 services are running.
If a bot has been silent (no process) for >1 check → sends Telegram alert to admin.
Also auto-restarts via launchctl if possible.

Run via LaunchAgent: com.threewordsdaily.watchdog.plist
"""

import asyncio
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ANALYST_BOT_TOKEN: str = os.getenv("ANALYST_BOT_TOKEN", "")
ADMIN_CHAT_ID: int = int(os.getenv("ADMIN_CHAT_ID", "0"))

logging.basicConfig(
    format="%(asctime)s [watchdog] %(levelname)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("watchdog")

# Service name → process keyword to grep for
SERVICES = {
    "learning_bot":      ("com.threewordsdaily.learning",    "learning_bot.py"),
    "content_publisher": ("com.threewordsdaily.content",     "content_publisher.py"),
    "teacher_bot":       ("com.threewordsdaily.teacher",     "teacher_bot.py"),
    "analyst_bot":       ("com.threewordsdaily.analyst",     "analyst_bot.py"),
    "marketer_bot":      ("com.threewordsdaily.marketer",    "marketer_bot.py"),
    "speak_bot":         ("com.threewordsdaily.speak",       "speak_bot.py"),
    "miniapp":           ("com.threewordsdaily.miniapp.v2",  "uvicorn"),
}


def is_running(keyword: str) -> bool:
    """Return True if a process matching keyword is alive."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", keyword],
            capture_output=True, text=True
        )
        return result.returncode == 0
    except Exception:
        return False


def kill_port(port: int) -> None:
    """Kill any process holding a TCP port (for miniapp port conflicts)."""
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, text=True
        )
        pids = result.stdout.strip().split()
        for pid in pids:
            if pid.isdigit():
                subprocess.run(["kill", "-9", pid], capture_output=True)
                log.info("Killed PID %s on port %d", pid, port)
    except Exception as exc:
        log.warning("kill_port(%d) error: %s", port, exc)


def restart_service(label: str, name: str = "") -> bool:
    """Kill port conflict if needed, then restart via launchctl."""
    try:
        # miniapp uses port 8000 — must free it before restart
        if name == "miniapp":
            kill_port(8000)
            import time; time.sleep(1)
        subprocess.run(
            ["/bin/launchctl", "kickstart", "-k", f"gui/{os.getuid()}/{label}"],
            capture_output=True, timeout=15
        )
        return True
    except Exception as exc:
        log.error("restart_service(%s) failed: %s", label, exc)
        return False


async def send_alert(text: str) -> None:
    """Send Telegram message to admin using Bot API directly (no library needed)."""
    if not ANALYST_BOT_TOKEN or not ADMIN_CHAT_ID:
        log.warning("ANALYST_BOT_TOKEN or ADMIN_CHAT_ID not set — cannot send alert")
        return
    try:
        import urllib.request
        import urllib.parse
        import json
        payload = json.dumps({
            "chat_id": ADMIN_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
        }).encode()
        url = f"https://api.telegram.org/bot{ANALYST_BOT_TOKEN}/sendMessage"
        req = urllib.request.Request(url, data=payload,
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
        log.info("Alert sent to admin")
    except Exception as exc:
        log.error("Failed to send alert: %s", exc)


async def check_all() -> None:
    down = []
    restarted = []

    for name, (label, keyword) in SERVICES.items():
        if not is_running(keyword):
            down.append(name)
            log.warning("⚠️  %s is DOWN — attempting restart", name)
            if restart_service(label, name):
                restarted.append(name)
                log.info("↻  %s restart triggered", name)

    if down:
        now = datetime.now().strftime("%d.%m %H:%M")
        down_list = "\n".join(f"  💀 {s}" for s in down)
        restart_list = "\n".join(f"  ↻ {s}" for s in restarted) if restarted else "  ❌ не вдалося"

        await send_alert(
            f"⚠️ <b>Watchdog Alert — {now}</b>\n\n"
            f"<b>Упали сервіси:</b>\n{down_list}\n\n"
            f"<b>Перезапущено:</b>\n{restart_list}\n\n"
            f"Перевір: <code>tail -50 ~/Desktop/ThreeWordsDaily_BOT/logs/*.log</code>"
        )
    else:
        log.info("✅ All %d services running", len(SERVICES))


async def main() -> None:
    log.info("Watchdog started — monitoring %d services", len(SERVICES))
    await check_all()


if __name__ == "__main__":
    asyncio.run(main())
