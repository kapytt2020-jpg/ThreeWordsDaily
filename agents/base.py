"""
agents/base.py — Claude Agent SDK Foundation Layer (Voodoo Platform)

Uses the official claude-agent-sdk package.
pip install claude-agent-sdk
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger("voodoo.agents")

# ── SDK import ────────────────────────────────────────────────────────────────
try:
    from claude_agent_sdk import (
        query,
        ClaudeAgentOptions,
        AgentDefinition,
        AssistantMessage,
        ResultMessage,
    )
    _SDK_AVAILABLE = True
except ImportError:
    _SDK_AVAILABLE = False
    log.warning("claude-agent-sdk not installed. Run: pip install claude-agent-sdk")

# Fallback: use raw Anthropic client if SDK not available
try:
    import anthropic as _anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False


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


# ── Result container ──────────────────────────────────────────────────────────

@dataclass
class AgentResult:
    agent: str
    success: bool
    output: str
    cost_usd: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# ── Core agentic runner ───────────────────────────────────────────────────────

async def run_agent_sdk(
    task: str,
    system_prompt: str = "",
    allowed_tools: Optional[list[str]] = None,
    subagents: Optional[dict[str, dict]] = None,
    max_turns: int = 10,
    cwd: Optional[str] = None,
) -> AgentResult:
    """
    Run a task using the Claude Agent SDK (claude-agent-sdk package).
    Returns AgentResult with the final output.
    """
    if not _SDK_AVAILABLE:
        return AgentResult(agent="sdk", success=False,
                           output="claude-agent-sdk not installed")

    tools = allowed_tools or ["Read", "Glob", "Grep", "WebSearch"]

    # Build subagent definitions if provided
    agent_defs: dict[str, AgentDefinition] = {}
    if subagents:
        tools = list(set(tools + ["Agent"]))
        for name, cfg in subagents.items():
            agent_defs[name] = AgentDefinition(
                description=cfg.get("description", ""),
                prompt=cfg.get("prompt", ""),
                tools=cfg.get("tools", ["Read", "Glob"]),
            )

    opts = ClaudeAgentOptions(
        allowed_tools=tools,
        system_prompt=system_prompt or "",
        max_turns=max_turns,
        cwd=cwd,
        agents=agent_defs if agent_defs else None,
    )

    output_parts: list[str] = []
    cost = 0.0

    async for message in query(prompt=task, options=opts):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if hasattr(block, "text") and block.text:
                    output_parts.append(block.text)
        elif isinstance(message, ResultMessage):
            cost = getattr(message, "cost_usd", 0.0) or 0.0

    result_text = "\n".join(output_parts).strip() or "No output"
    return AgentResult(agent="sdk", success=True, output=result_text, cost_usd=cost)


def run_agent_sdk_sync(task: str, system_prompt: str = "", **kwargs) -> AgentResult:
    """Synchronous wrapper for run_agent_sdk."""
    return asyncio.run(run_agent_sdk(task, system_prompt, **kwargs))


# ── Fallback: raw Anthropic client (no SDK) ───────────────────────────────────

def run_agent_anthropic(
    system_prompt: str,
    user_message: str,
    model: str = "claude-opus-4-6",
    max_tokens: int = 2000,
) -> str:
    """Direct Anthropic API call — used when Agent SDK is unavailable."""
    if not _ANTHROPIC_AVAILABLE:
        return "ERROR: anthropic package not installed"
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "ERROR: ANTHROPIC_API_KEY not set"
    client = _anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text.strip()


async def run_agent_anthropic_async(system_prompt: str, user_message: str, **kwargs) -> str:
    return await asyncio.to_thread(run_agent_anthropic, system_prompt, user_message, **kwargs)


# ── Universal dispatcher ───────────────────────────────────────────────────────

async def ask_agent(
    system_prompt: str,
    task: str,
    use_sdk: bool = False,
    **kwargs,
) -> str:
    """
    Universal agent call. Tries SDK first if use_sdk=True, falls back to Anthropic API.
    """
    if use_sdk and _SDK_AVAILABLE:
        result = await run_agent_sdk(task=task, system_prompt=system_prompt, **kwargs)
        return result.output
    else:
        return await run_agent_anthropic_async(system_prompt, task)


# ── Subagent spawner ──────────────────────────────────────────────────────────

async def spawn_subagent_async(
    agent_name: str,
    system_prompt: str,
    task: str,
    use_sdk: bool = False,
    **kwargs,
) -> AgentResult:
    """Spawn a named subagent for a specific task."""
    log.info("Spawning subagent: %s", agent_name)
    try:
        output = await ask_agent(system_prompt, task, use_sdk=use_sdk, **kwargs)
        return AgentResult(agent=agent_name, success=True, output=output)
    except Exception as exc:
        log.error("Subagent %s failed: %s", agent_name, exc)
        return AgentResult(agent=agent_name, success=False, output=str(exc))


def spawn_subagent(agent_name: str, system_prompt: str, task: str, **kwargs) -> AgentResult:
    return asyncio.run(spawn_subagent_async(agent_name, system_prompt, task, **kwargs))


# Run used by teacher/analyst for simple AI calls
def run_agent(system_prompt: str, user_message: str, tools: list = None, **kwargs) -> str:
    """Sync helper used by bots that need a quick AI response."""
    return run_agent_anthropic(system_prompt, user_message)
