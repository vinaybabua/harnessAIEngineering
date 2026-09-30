"""Defines the single ADK banking agent used throughout this project.

Discoverable by the `adk web` / `adk run` CLI: this module exposes a
module-level `root_agent`, and `app/__init__.py` imports this module.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.agents.context import Context
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.base_tool import BaseTool

from app import audit, limits
from app.prompts import SYSTEM_PROMPT
from app.tools.banking_tools import (
    confirm_transfer,
    get_all_balances,
    find_beneficiaries,
    get_balance,
    get_transaction_status,
    initiate_transfer,
)

load_dotenv(Path(__file__).parent / ".env")

AGENT_NAME = "banking_agent"


def _log_user_request(callback_context: Context) -> None:
    """One USER_REQUEST audit event per user turn.

    This is cross-cutting lifecycle logging that applies regardless of what
    the user asked for, so it belongs in ADK's callback layer rather than
    in any individual tool. ADK invokes this with `callback_context=...`.
    """
    text = None
    if callback_context.user_content and callback_context.user_content.parts:
        text = callback_context.user_content.parts[0].text
    audit.log("USER_REQUEST", text=text)
    return None


def _enforce_tool_limits(
    tool: BaseTool, args: dict[str, Any], tool_context: Context
) -> dict[str, Any] | None:
    """MAX_TOOL_CALLS gate + TOOL_REQUESTED audit event, for every tool call.

    The limit itself and the counting live in app/limits.py; this callback
    only triggers the check. Transfer-specific limits (attempts, repeated
    identical failures) are banking business rules, so they live with the
    transfer logic in app/tools/banking_tools.py instead of here. ADK
    invokes this with `tool=...`, `args=...`, `tool_context=...`.
    """
    if not limits.register_tool_call():
        audit.log("LIMIT_EXCEEDED", limit="MAX_TOOL_CALLS", tool=tool.name)
        return {
            "status": "BLOCKED",
            "reason": "Maximum tool calls reached for this session.",
        }
    audit.log("TOOL_REQUESTED", tool=tool.name, args=args)
    return None


root_agent = Agent(
    name=AGENT_NAME,
    model=LiteLlm(model=os.environ["LLM_MODEL"]),
    description=(
        "Banking assistant for checking balance, finding beneficiaries, "
        "transferring money, and checking transaction status."
    ),
    instruction=SYSTEM_PROMPT,
    tools=[get_balance,get_all_balances, find_beneficiaries, initiate_transfer, confirm_transfer, get_transaction_status],
    before_agent_callback=_log_user_request,
    before_tool_callback=_enforce_tool_limits,
)
