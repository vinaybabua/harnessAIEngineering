"""Deterministic execution limits.

The thresholds, and what happens when they're hit, live here in plain
Python. Callers (ADK callbacks or tool functions) only trigger a check and
act on the boolean result — the counting and the decision both live here.
"""

from __future__ import annotations

import os

MAX_TOOL_CALLS = int(os.environ.get("MAX_TOOL_CALLS", "20"))
MAX_TRANSFER_ATTEMPTS = int(os.environ.get("MAX_TRANSFER_ATTEMPTS", "5"))
MAX_IDENTICAL_FAILURES = int(os.environ.get("MAX_IDENTICAL_FAILURES", "3"))

_tool_call_count = 0
_transfer_attempt_count = 0
_last_failure_signature: str | None = None
_identical_failure_streak = 0


def register_tool_call() -> bool:
    """Count a tool call. Returns False once MAX_TOOL_CALLS is exceeded."""
    global _tool_call_count
    _tool_call_count += 1
    return _tool_call_count <= MAX_TOOL_CALLS


def register_transfer_attempt() -> bool:
    """Count a transfer attempt. Returns False once MAX_TRANSFER_ATTEMPTS is exceeded."""
    global _transfer_attempt_count
    _transfer_attempt_count += 1
    return _transfer_attempt_count <= MAX_TRANSFER_ATTEMPTS


def record_transfer_outcome(is_rejection: bool, signature: str | None = None) -> bool:
    """Track consecutive identical rejections.

    Returns False once the same rejection reason has repeated
    MAX_IDENTICAL_FAILURES times in a row. Any non-rejection outcome
    (approved, or needs clarification) resets the streak.
    """
    global _last_failure_signature, _identical_failure_streak
    if not is_rejection:
        _last_failure_signature = None
        _identical_failure_streak = 0
        return True
    if signature == _last_failure_signature:
        _identical_failure_streak += 1
    else:
        _last_failure_signature = signature
        _identical_failure_streak = 1
    return _identical_failure_streak <= MAX_IDENTICAL_FAILURES
