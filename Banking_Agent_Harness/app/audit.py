"""Centralized audit logging.

Every event is appended to an in-memory list and printed to stdout — the
terminal running `adk web` — so the harness's decisions are visible during
a demo. Never log API keys, secrets, chain-of-thought, or full account
numbers; only structured banking events.
"""

from __future__ import annotations

import logging
from typing import Any

_logger = logging.getLogger("banking_agent.audit")
if not _logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[AUDIT] %(message)s"))
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False

_events: list[dict[str, Any]] = []


def log(event_type: str, **details: Any) -> None:
    entry = {"event": event_type, **details}
    _events.append(entry)
    detail_str = " ".join(f"{k}={v!r}" for k, v in details.items())
    _logger.info("%s %s", event_type, detail_str)


def events() -> list[dict[str, Any]]:
    """All audit events recorded so far, oldest first."""
    return list(_events)
