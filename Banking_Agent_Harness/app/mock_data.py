"""In-memory mock banking data. This is the single source of truth for the POC."""

from __future__ import annotations

import copy
from typing import Any

ACCOUNT_ID = "Savings_001"

_INITIAL_ACCOUNTS: dict[str, dict[str, Any]] = {
    ACCOUNT_ID: {
        "balance": 200000,
        "status": "ACTIVE",
        "type": "savings",
        "daily_limit": 100000,
        "daily_used": 25000,
    },
    "SAVINGS_002": {
        "balance": 50000,
        "status": "ACTIVE",
        "type": "savings",        
        "daily_limit": 30000,
        "daily_used": 0,
    },
    "Checking_002": {
            "balance": 30000,
            "status": "ACTIVE",
            "type": "checking",
            "daily_limit": 5000,
            "daily_used": 0,
        },
}

_INITIAL_BENEFICIARIES: list[dict[str, str]] = [
    {"id": "B1", "name": "John Smith", "status": "ACTIVE", "account_number": "1234567890123456"},
    {"id": "B2", "name": "John Luis", "status": "ACTIVE", "account_number": "2345678901234567"},
    {"id": "B3", "name": "Aaron Johnson", "status": "ACTIVE", "account_number": "3456789012345678"},
    {"id": "B4", "name": "Nick Anderson", "status": "BLOCKED", "account_number": "4567890123456789"},
]

accounts: dict[str, dict[str, Any]] = copy.deepcopy(_INITIAL_ACCOUNTS)
beneficiaries: list[dict[str, str]] = copy.deepcopy(_INITIAL_BENEFICIARIES)
transactions: dict[str, dict[str, Any]] = {}

_transaction_counter = 0


def reset_state() -> None:
    """Restore all mock state to its initial values. Used between tests and demo runs."""
    global accounts, beneficiaries, transactions, _transaction_counter
    accounts = copy.deepcopy(_INITIAL_ACCOUNTS)
    beneficiaries = copy.deepcopy(_INITIAL_BENEFICIARIES)
    transactions = {}
    _transaction_counter = 0


def next_transaction_id() -> str:
    global _transaction_counter
    _transaction_counter += 1
    return f"TXN{_transaction_counter:03d}"


def resolve_beneficiaries(query: str) -> list[dict[str, str]]:
    """Match by case-insensitive name substring, exact id, or exact last-4 account digits."""
    query_stripped = query.strip()
    query_lower = query_stripped.lower()
    return [
        b
        for b in beneficiaries
        if query_lower in b["name"].lower()
        or query_lower == b["id"].lower()
        or query_stripped == mask_account_number(b["account_number"])
    ]


def mask_account_number(account_number: str) -> str:
    return account_number[-4:]


def public_beneficiary(beneficiary: dict[str, str]) -> dict[str, str]:
    """Beneficiary view safe to expose to the model: no full account number."""
    return {
        "id": beneficiary["id"],
        "name": beneficiary["name"],
        "status": beneficiary["status"],
        "account_last4": mask_account_number(beneficiary["account_number"]),
    }
