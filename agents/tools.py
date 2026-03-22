"""
agents/tools.py — Platform tools available to agents

Register all tools that Claude agents can call.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.base import register_tool
from database import db


# ── Analytics tools ──────────────────────────────────────────────────────────

@register_tool(
    name="get_platform_stats",
    description="Get real-time platform statistics: users, activity, XP, streaks.",
    input_schema={"type": "object", "properties": {}, "required": []},
)
def get_platform_stats() -> dict:
    import asyncio
    return asyncio.run(db.get_stats())


@register_tool(
    name="get_top_users",
    description="Get top N users by XP for leaderboard or rewards.",
    input_schema={
        "type": "object",
        "properties": {"limit": {"type": "integer", "default": 10}},
        "required": [],
    },
)
def get_top_users(limit: int = 10) -> list:
    import asyncio
    stats = asyncio.run(db.get_stats())
    return stats.get("top10", [])[:limit]


@register_tool(
    name="get_recent_ops_log",
    description="Read recent operations log entries.",
    input_schema={
        "type": "object",
        "properties": {"limit": {"type": "integer", "default": 20}},
        "required": [],
    },
)
def get_recent_ops_log(limit: int = 20) -> list:
    conn = db._connect()
    rows = conn.execute(
        "SELECT actor, action, target, detail, ts FROM ops_log ORDER BY ts DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Content tools ─────────────────────────────────────────────────────────────

@register_tool(
    name="get_pending_content",
    description="Get content items scheduled but not yet posted.",
    input_schema={"type": "object", "properties": {}, "required": []},
)
def get_pending_content() -> list:
    conn = db._connect()
    rows = conn.execute(
        "SELECT * FROM content_plan WHERE status='pending' ORDER BY scheduled_at LIMIT 5"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@register_tool(
    name="schedule_content",
    description="Add a content item to the publishing queue.",
    input_schema={
        "type": "object",
        "properties": {
            "scheduled_at": {"type": "string", "description": "ISO datetime"},
            "content_type": {"type": "string", "enum": ["word", "quiz", "recap", "challenge"]},
            "topic": {"type": "string"},
            "post_text": {"type": "string"},
        },
        "required": ["scheduled_at", "content_type", "post_text"],
    },
)
def schedule_content(scheduled_at: str, content_type: str, post_text: str, topic: str = "") -> str:
    conn = db._connect()
    conn.execute(
        "INSERT INTO content_plan (scheduled_at, content_type, topic, post_text) VALUES (?,?,?,?)",
        (scheduled_at, content_type, topic, post_text)
    )
    conn.commit()
    conn.close()
    return f"Scheduled: {content_type} at {scheduled_at}"


# ── Service management tools ──────────────────────────────────────────────────

SERVICES = {
    "voodoo_bot":       ("com.voodoo.bot",       "voodoo_bot.py"),
    "speak_bot":        ("com.voodoo.speak",      "voodoo_speak_bot.py"),
    "teacher_bot":      ("com.voodoo.teacher",    "voodoo_teacher_bot.py"),
    "publisher_bot":    ("com.voodoo.publisher",  "voodoo_publisher_bot.py"),
    "analyst_bot":      ("com.voodoo.analyst",    "voodoo_analyst_bot.py"),
    "growth_bot":       ("com.voodoo.growth",     "voodoo_growth_bot.py"),
    "ops_bot":          ("com.voodoo.ops",        "voodoo_ops_bot.py"),
    "test_bot":         ("com.voodoo.test",       "voodoo_test_bot.py"),
    "miniapp":          ("com.voodoo.miniapp",    "uvicorn"),
}


@register_tool(
    name="check_service_status",
    description="Check if a bot/service process is running.",
    input_schema={
        "type": "object",
        "properties": {
            "service": {"type": "string", "description": "Service name, or 'all' for all services"}
        },
        "required": ["service"],
    },
)
def check_service_status(service: str) -> dict:
    import subprocess
    results = {}
    targets = SERVICES.items() if service == "all" else (
        [(service, SERVICES[service])] if service in SERVICES else []
    )
    for name, (label, keyword) in targets:
        r = subprocess.run(["pgrep", "-f", keyword], capture_output=True)
        results[name] = "running" if r.returncode == 0 else "stopped"
    return results


@register_tool(
    name="restart_service",
    description="Restart a bot/service via launchctl. Use with care.",
    input_schema={
        "type": "object",
        "properties": {
            "service": {"type": "string", "description": "Service name to restart"},
            "confirmed": {"type": "boolean", "description": "Must be true to execute"},
        },
        "required": ["service", "confirmed"],
    },
)
def restart_service(service: str, confirmed: bool) -> str:
    if not confirmed:
        return "Restart not confirmed. Set confirmed=true to proceed."
    import os
    svc = SERVICES.get(service)
    if not svc:
        return f"Unknown service: {service}"
    label = svc[0]
    try:
        subprocess.run(
            ["/bin/launchctl", "kickstart", "-k", f"gui/{os.getuid()}/{label}"],
            capture_output=True, timeout=15
        )
        return f"Restart triggered: {service} ({label})"
    except Exception as e:
        return f"Restart failed: {e}"


@register_tool(
    name="read_service_logs",
    description="Read last N lines of a service log file.",
    input_schema={
        "type": "object",
        "properties": {
            "service": {"type": "string"},
            "lines": {"type": "integer", "default": 30},
        },
        "required": ["service"],
    },
)
def read_service_logs(service: str, lines: int = 30) -> str:
    log_dir = Path(__file__).parent.parent / "logs"
    log_file = log_dir / f"{service}.log"
    if not log_file.exists():
        return f"Log not found: {log_file}"
    text = log_file.read_text(errors="replace").splitlines()
    return "\n".join(text[-lines:])


# ── Approval tools ────────────────────────────────────────────────────────────

@register_tool(
    name="create_approval_request",
    description="Create an approval request that VoodooOpsBot admin must approve before action.",
    input_schema={
        "type": "object",
        "properties": {
            "request_by": {"type": "string"},
            "action_type": {"type": "string"},
            "payload": {"type": "object"},
        },
        "required": ["request_by", "action_type", "payload"],
    },
)
def create_approval_request(request_by: str, action_type: str, payload: dict) -> dict:
    import asyncio
    approval_id = asyncio.run(
        db.create_approval(request_by, action_type, json.dumps(payload))
    )
    return {"approval_id": approval_id, "status": "pending", "message": "Awaiting admin approval"}


@register_tool(
    name="get_pending_approvals",
    description="List all approval requests awaiting admin decision.",
    input_schema={"type": "object", "properties": {}, "required": []},
)
def get_pending_approvals() -> list:
    conn = db._connect()
    rows = conn.execute(
        "SELECT * FROM approvals WHERE status='pending' ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
