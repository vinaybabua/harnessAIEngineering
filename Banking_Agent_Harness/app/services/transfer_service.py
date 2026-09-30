"""In-memory pending-transfer state.

A single pending slot is enough for this single-session demo — no database
or workflow engine needed. Requiring `confirm_transfer` to execute against
this real state (instead of exposing a tool parameter like
`skip_confirmation`) is what makes confirmation deterministic: the model can
be asked to skip it, but there is no code path that lets it.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PendingTransfer:
    beneficiary_id: str
    beneficiary_name: str
    account_last4: str
    amount: float
    account_id: str   # <-- new: which account this transfer debits from


_pending: PendingTransfer | None = None


def set_pending(transfer: PendingTransfer) -> None:
    global _pending
    _pending = transfer


def get_pending() -> PendingTransfer | None:
    return _pending


def clear_pending() -> None:
    global _pending
    _pending = None