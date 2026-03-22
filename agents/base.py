"""
agents/base.py — Voodoo Platform Agent Foundation

TWO layers:
  1. claude-agent-sdk  — autonomous research/planning/improvement agents
                         (spawns a real Claude Code subprocess with full tools)
  2. anthropic API     — real-time responses in bots (content, analysis, teaching)

Use SDK for:  autonomous tasks, multi-step research, codebase analysis, improvement loops
Use API for:  instant bot replies, content generation, quiz/word generation
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger("voodoo.agents")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY", "")

# ── System prompts ────────────────────────────────────────────────────────────

PLANNER_SYSTEM = """Ти — Voodoo Platform Planner. Розбиваєш задачі на конкретні кроки.
Відповідаєш українською. Будь конкретним і actionable."""

ANALYST_SYSTEM = """Ти — Voodoo Analytics Agent. Аналізуєш реальні дані платформи.
Правила: тільки реальні числа, конкретні рекомендації, відповідь українською.
Формат: HTML Telegram (<b>, <i>). Коротко і по суті."""

CONTENT_SYSTEM = """Ти — Voodoo Content Agent. Створюєш контент для вивчення англійської.
Аудиторія: українськомовні користувачі. Рівні: A1-C1.
Формат Telegram HTML. Контент: живий, цікавий, корисний."""

OPS_SYSTEM = """Ти — Voodoo Ops Agent. Моніториш сервіси, координуєш задачі.
Консервативний з деструктивними діями. Завжди підтверджуй перед критичними операціями."""

TEACHER_SYSTEM = """Ти — Voodoo Teacher AI. Пояснюєш англійську українськомовним студентам.
Включай IPA вимову, приклади, типові помилки. Відповідь: max 300 слів, HTML формат."""

RESEARCH_SYSTEM = """You are a Voodoo Platform Research Agent.
Research task thoroughly using available tools (WebSearch, WebFetch, Read, Glob, Grep).
Return actionable, specific findings. Focus on what can be immediately implemented."""


# ── Result containers ─────────────────────────────────────────────────────────

@dataclass
class AgentResult:
    agent: str
    success: bool
    output: str
    cost_usd: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# ── Layer 1: Claude Agent SDK (autonomous agents) ────────────────────────────

async def run_sdk_agent(
    task: str,
    system_prompt: str = "",
    allowed_tools: Optional[list[str]] = None,
    cwd: Optional[str] = None,
    max_turns: int = 15,
) -> AgentResult:
    """
    Run an autonomous agent using the Claude Agent SDK.
    This spawns a full Claude Code subprocess that can use Read/Write/Bash/WebSearch etc.
    Best for: research, codebase analysis, multi-step autonomous tasks.
    """
    try:
        from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, ResultMessage
    except ImportError:
        log.warning("claude-agent-sdk not installed, falling back to API")
        output = await _anthropic_call(system_prompt or RESEARCH_SYSTEM, task)
        return AgentResult(agent="api_fallback", success=True, output=output)

    tools = allowed_tools or ["Read", "Glob", "Grep", "WebSearch", "WebFetch", "Bash"]
    options = ClaudeAgentOptions(
        allowed_tools=tools,
        system_prompt=system_prompt,
        max_turns=max_turns,
        cwd=cwd or str(os.getcwd()),
    )

    output_parts: list[str] = []
    cost = 0.0

    try:
        async for message in query(prompt=task, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if hasattr(block, "text") and block.text:
                        output_parts.append(block.text)
            elif isinstance(message, ResultMessage):
                cost = getattr(message, "cost_usd", 0.0) or 0.0

        result_text = "\n".join(output_parts).strip() or "No output"
        return AgentResult(agent="sdk", success=True, output=result_text, cost_usd=cost)

    except Exception as exc:
        log.error("SDK agent failed: %s", exc)
        # Fallback to raw API
        output = await _anthropic_call(system_prompt or RESEARCH_SYSTEM, task)
        return AgentResult(agent="api_fallback", success=True, output=output)


# ── Layer 2: OpenAI GPT (fast bot responses to users) ────────────────────────

async def _anthropic_call(
    system_prompt: str,
    user_message: str,
    model: str = "gpt-4o",
    max_tokens: int = 2000,
) -> str:
    """Real-time bot responses via OpenAI GPT-4o."""
    if not OPENAI_API_KEY:
        return "ERROR: OPENAI_API_KEY not set in .env"
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_message},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        log.error("OpenAI API call failed: %s", exc)
        return f"AI помилка: {exc}"


async def ask_agent(system_prompt: str, task: str, use_sdk: bool = False, **kwargs) -> str:
    """
    Universal call. use_sdk=True for autonomous multi-step tasks.
    use_sdk=False (default) for fast real-time bot replies.
    """
    if use_sdk:
        result = await run_sdk_agent(task=task, system_prompt=system_prompt, **kwargs)
        return result.output
    return await _anthropic_call(system_prompt, task)


# ── Subagent spawner ──────────────────────────────────────────────────────────

async def spawn_subagent_async(
    agent_name: str,
    system_prompt: str,
    task: str,
    use_sdk: bool = False,
    **kwargs,
) -> AgentResult:
    log.info("Spawning: %s (sdk=%s)", agent_name, use_sdk)
    try:
        output = await ask_agent(system_prompt, task, use_sdk=use_sdk, **kwargs)
        return AgentResult(agent=agent_name, success=True, output=output)
    except Exception as exc:
        log.error("Subagent %s failed: %s", agent_name, exc)
        return AgentResult(agent=agent_name, success=False, output=str(exc))


def spawn_subagent(agent_name: str, system_prompt: str, task: str, **kwargs) -> AgentResult:
    return asyncio.run(spawn_subagent_async(agent_name, system_prompt, task, **kwargs))


def run_agent(system_prompt: str, user_message: str, tools: list = None, **kwargs) -> str:
    """Sync helper for bot handlers that need a quick AI response."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _anthropic_call(system_prompt, user_message))
                return future.result(timeout=30)
        return loop.run_until_complete(_anthropic_call(system_prompt, user_message))
    except Exception as e:
        return f"Error: {e}"


# ── Compatibility ─────────────────────────────────────────────────────────────

def register_tool(name: str, description: str, input_schema: dict):
    """No-op decorator shim for tools.py compatibility."""
    def decorator(fn):
        return fn
    return decorator


# ── Autonomous improvement loop ───────────────────────────────────────────────

async def run_improvement_agent(
    target: str = "platform",
    post_to_group: bool = True,
) -> AgentResult:
    """
    Autonomous agent that:
    1. Searches GitHub/web for new patterns relevant to the platform
    2. Analyzes current codebase
    3. Proposes improvements
    4. Posts findings to internal group (Agent-Talk topic)
    """
    task = (
        f"Research improvements for the Voodoo English Learning Telegram platform.\n\n"
        f"Target: {target}\n\n"
        f"Tasks:\n"
        f"1. Search GitHub for: telegram bot gamification, telegram mini app retention, "
        f"   english learning telegram bot best practices\n"
        f"2. Read key platform files in /Users/usernew/Desktop/VoodooBot/\n"
        f"3. Identify top 3 improvements that can be implemented today\n"
        f"4. Return specific, actionable recommendations with code examples\n\n"
        f"Focus on: retention, engagement, monetization, UX."
    )

    result = await run_sdk_agent(
        task=task,
        system_prompt=RESEARCH_SYSTEM,
        allowed_tools=["Read", "Glob", "Grep", "WebSearch", "WebFetch"],
        cwd="/Users/usernew/Desktop/VoodooBot",
        max_turns=20,
    )

    if post_to_group and result.success:
        try:
            from agents.group_poster import agent_discussion
            await agent_discussion(
                f"🤖 <b>Improvement Research — {datetime.now().strftime('%d.%m %H:%M')}</b>\n\n"
                + result.output[:3000]
            )
        except Exception:
            pass

    return result
