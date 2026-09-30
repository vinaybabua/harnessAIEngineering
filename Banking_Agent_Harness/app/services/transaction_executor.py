"""Decides the real outcome of an executed transfer.

Kept separate from `confirm_transfer` on purpose: a tool call succeeding
(no exception, a return value) must never be confused with the underlying
transfer succeeding. The verified outcome always comes from here.

For this demo, the outcome is controlled by the MOCK_TRANSACTION_OUTCOME
env var (SUCCESS by default). Set it to FAILED or PENDING in app/.env and
restart `adk web` to demo those paths, without adding any conditional logic
to the agent or tool layer.
"""

from __future__ import annotations

import os

VALID_OUTCOMES = {"SUCCESS", "FAILED", "PENDING"}


def execute() -> str:
    outcome = os.environ.get("MOCK_TRANSACTION_OUTCOME", "SUCCESS").strip().upper()
    return outcome if outcome in VALID_OUTCOMES else "SUCCESS"
