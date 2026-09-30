"""Deterministic transfer validation.

The LLM may request any transfer it likes; whether it actually happens is
decided entirely here, in plain Python — never by the system prompt.
"""

from __future__ import annotations

from dataclasses import dataclass

from app import mock_data


@dataclass
class TransferValidation:
    status: str  # "APPROVED" | "REJECTED"
    beneficiary: dict[str, str] | None = None
    reason: str | None = None


def validate_transfer(
    beneficiary: dict[str, str],
    amount: float,
    account_id: str,
) -> TransferValidation:
    """Validate a transfer against a single, already-resolved beneficiary and account.

    Beneficiary and account ambiguity/lookup is handled upstream in
    initiate_transfer — this function only applies deterministic business
    rules (status, amount, balance, daily limit) to the exact beneficiary
    and account given.
    """
    if amount <= 0:
        return TransferValidation(
            status="REJECTED", reason="Transfer amount must be greater than zero."
        )

    account = mock_data.accounts[account_id]
    if account["status"] != "ACTIVE":
        return TransferValidation(status="REJECTED", reason="Your account is not active.")

    if beneficiary["status"] != "ACTIVE":
        return TransferValidation(
            status="REJECTED",
            reason=f"Beneficiary '{beneficiary['name']}' is blocked and cannot receive transfers.",
        )

    if amount > account["balance"]:
        return TransferValidation(status="REJECTED", reason="Insufficient account balance.")

    if account["daily_used"] + amount > account["daily_limit"]:
        remaining = account["daily_limit"] - account["daily_used"]
        return TransferValidation(
            status="REJECTED",
            reason=f"Daily transfer limit exceeded. Only {remaining} remains today.",
        )

    return TransferValidation(status="APPROVED", beneficiary=beneficiary)