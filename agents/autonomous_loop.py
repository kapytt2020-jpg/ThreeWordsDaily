"""
agents/autonomous_loop.py — Voodoo Autonomous Improvement Loop

Runs on schedule. Uses Claude Agent SDK to:
1. Research new Telegram/gamification patterns (GitHub, web)
2. Analyze platform performance
3. Generate improvement proposals
4. Post to internal group (Agent-Talk topic)
5. Create approval requests in VoodooOpsBot

Schedule:
  Daily   03:00 — Research new patterns + GitHub scan
  Weekly  Sun 22:00 — Full platform improvement proposal
  Daily   21:00 — Self-analysis: what the platform should improve
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("autonomous_loop")
KYIV_TZ = ZoneInfo("Europe/Kyiv")


async def research_github_patterns() -> str:
    """Search GitHub for best practices to apply to Voodoo."""
    from agents.base import run_sdk_agent, RESEARCH_SYSTEM

    return (await run_sdk_agent(
        task=(
            "Search GitHub and web for the LATEST patterns in:\n"
            "1. Telegram Mini App gamification (stars, pets, streaks)\n"
            "2. Language learning retention mechanics (Duolingo-style)\n"
            "3. Telegram bot monetization (Stars payments, subscriptions)\n"
            "4. Python-telegram-bot 21.x new features\n\n"
            "For each finding: explain what it is, how to apply to Voodoo platform, "
            "and give a short code snippet if possible.\n"
            "Return top 5 most actionable findings."
        ),
        system_prompt=RESEARCH_SYSTEM,
        allowed_tools=["WebSearch", "WebFetch"],
        max_turns=10,
    )).output


async def analyze_platform_health() -> str:
    """Analyze platform metrics and suggest improvements."""
    from agents.base import run_sdk_agent, ANALYST_SYSTEM
    from database import db

    stats = await db.get_stats()

    return (await run_sdk_agent(
        task=(
            f"Analyze this Voodoo platform data and suggest concrete improvements:\n"
            f"{json.dumps(stats, ensure_ascii=False, indent=2)}\n\n"
            f"Identify:\n"
            f"1. Biggest retention risk\n"
            f"2. Best growth opportunity\n"
            f"3. One quick win to implement today\n"
            f"Reply in Ukrainian, max 200 words."
        ),
        system_prompt=ANALYST_SYSTEM,
        allowed_tools=[],
        max_turns=3,
    )).output


async def generate_improvement_proposal() -> str:
    """Full weekly improvement proposal using SDK to read codebase."""
    from agents.base import run_sdk_agent, RESEARCH_SYSTEM

    return (await run_sdk_agent(
        task=(
            "You are analyzing the Voodoo English Learning Platform codebase.\n\n"
            "Tasks:\n"
            "1. Read /Users/usernew/Desktop/VoodooBot/bots/voodoo_bot.py\n"
            "2. Read /Users/usernew/Desktop/VoodooBot/miniapp/app.js (first 100 lines)\n"
            "3. Read /Users/usernew/Desktop/VoodooBot/database/db.py\n"
            "4. Based on what you see, propose the TOP 3 improvements:\n"
            "   - What to add/change\n"
            "   - Why it will help retention/growth\n"
            "   - Rough implementation plan\n\n"
            "Reply in Ukrainian. Be specific and code-oriented."
        ),
        system_prompt=RESEARCH_SYSTEM,
        allowed_tools=["Read", "Glob"],
        cwd="/Users/usernew/Desktop/VoodooBot",
        max_turns=8,
    )).output


async def post_to_group(agent: str, text: str) -> None:
    """Post result to internal group topic."""
    try:
        from agents.group_poster import post_to_group as _post
        await _post(agent, text)
    except Exception as e:
        log.debug("Group post failed: %s", e)


async def create_approval_for_improvement(proposal: str) -> None:
    """Create an approval request in VoodooOpsBot for the improvement."""
    try:
        from database import db
        await db.create_approval(
            request_by="autonomous_loop",
            action_type="platform_improvement",
            payload=json.dumps({
                "proposal": proposal[:1000],
                "timestamp": datetime.now().isoformat(),
                "auto_generated": True,
            })
        )
        log.info("Approval request created for improvement proposal")
    except Exception as e:
        log.error("Failed to create approval: %s", e)


async def run_weekly_podcast() -> None:
    """Mon 09:00 — Generate and post weekly podcast to group topic."""
    log.info("Starting weekly podcast generation...")
    try:
        from agents.podcast_agent import generate_and_send_weekly
        ok = await generate_and_send_weekly(post_to_group=True)
        log.info("Weekly podcast: %s", "posted" if ok else "failed")
    except Exception as e:
        log.error("Weekly podcast failed: %s", e)


async def run_daily_research() -> None:
    """03:00 — Daily GitHub/web research."""
    log.info("Starting daily research...")
    try:
        findings = await research_github_patterns()
        await post_to_group("agent",
            f"🔍 <b>Щоденний Research — {datetime.now().strftime('%d.%m %H:%M')}</b>\n\n"
            f"{findings[:3000]}"
        )
        log.info("Daily research posted to group")
    except Exception as e:
        log.error("Daily research failed: %s", e)


async def run_daily_analysis() -> None:
    """21:00 — Daily platform analysis."""
    log.info("Starting daily analysis...")
    try:
        analysis = await analyze_platform_health()
        await post_to_group("analyst",
            f"📊 <b>Денний аналіз — {datetime.now().strftime('%d.%m %H:%M')}</b>\n\n"
            f"{analysis}"
        )
        log.info("Daily analysis posted to group")
    except Exception as e:
        log.error("Daily analysis failed: %s", e)


async def run_weekly_improvement() -> None:
    """Sun 22:00 — Weekly codebase improvement proposal."""
    log.info("Starting weekly improvement proposal...")
    try:
        proposal = await generate_improvement_proposal()
        await post_to_group("agent",
            f"🚀 <b>Тижнева пропозиція покращень — {datetime.now().strftime('%d.%m')}</b>\n\n"
            f"{proposal[:3000]}"
        )
        # Create approval request for admin
        await create_approval_for_improvement(proposal)
        log.info("Weekly improvement proposal posted + approval created")
    except Exception as e:
        log.error("Weekly improvement failed: %s", e)


# ── Scheduler ─────────────────────────────────────────────────────────────────

async def main_loop() -> None:
    """Run the autonomous improvement loop indefinitely."""
    log.info("Autonomous loop started")
    sent: set[str] = set()

    while True:
        now     = datetime.now(KYIV_TZ)
        hour    = now.hour
        weekday = now.weekday()  # 6 = Sunday
        day_key = now.strftime("%Y-%m-%d")

        # Daily research at 03:00
        key_research = f"research_{day_key}"
        if hour == 3 and key_research not in sent:
            await run_daily_research()
            sent.add(key_research)

        # Daily analysis at 21:00
        key_analysis = f"analysis_{day_key}"
        if hour == 21 and key_analysis not in sent:
            await run_daily_analysis()
            sent.add(key_analysis)

        # Weekly improvement Sunday 22:00
        key_weekly = f"weekly_{day_key}"
        if weekday == 6 and hour == 22 and key_weekly not in sent:
            await run_weekly_improvement()
            sent.add(key_weekly)

        # Weekly podcast Monday 09:00 Kyiv
        key_podcast = f"podcast_{day_key}"
        if weekday == 0 and hour == 9 and key_podcast not in sent:
            await run_weekly_podcast()
            sent.add(key_podcast)

        # Cleanup old keys daily at midnight
        if hour == 0:
            sent = {k for k in sent if day_key in k}

        await asyncio.sleep(50)


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s [auto_loop] %(levelname)s %(message)s",
        level=logging.INFO,
    )
    asyncio.run(main_loop())
