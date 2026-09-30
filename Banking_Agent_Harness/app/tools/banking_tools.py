"""Thin tool functions the banking agent can call.

Transfers are a two-step, code-enforced flow: `initiate_transfer` validates
and stages a request, `confirm_transfer` executes only a request that was
actually staged. The model cannot talk its way past a rejected, ambiguous,
or unconfirmed request.
"""

from __future__ import annotations

from typing import Any

from app import audit, limits, mock_data
from app.services import policy_service, transaction_executor, transfer_service

def _format(acc_id: str) -> dict[str, Any]:
    account = mock_data.accounts[acc_id]
    return {
        "account": acc_id,
        "balance": account["balance"],
        "status": account["status"],
        "daily_limit": account["daily_limit"],
        "daily_used": account["daily_used"],
    }

def get_balance(account_id: str | None = None) -> dict[str, Any] | list[dict[str, Any]]:
    """Return balance, status, and daily transfer limit usage for a specific account
    (or all matching accounts, if the identifier matches more than one — e.g. multiple
    checking accounts).

    Args:
        account_id: A real account ID or a type like "savings"/"checking".
            If omitted, defaults to the user's primary account.

    Returns:
        A single account dict if there's exactly one match, or a list of
        account dicts if multiple accounts match the given type.
    """
    if account_id is None:
        # No account specified — check how many accounts the user actually has
        all_account_ids = list(mock_data.accounts.keys())

        if len(all_account_ids) > 1:
            return {
                "error": True,
                "message": "You have multiple accounts. Please specify which account you want to check.",
                "candidates": [
                    {"account": acc_id, "type": mock_data.accounts[acc_id].get("type", "unknown")}
                    for acc_id in all_account_ids
                ],
            }

        # Only one account exists -> safe to default to it
        resolved_ids = all_account_ids
    else:
        resolved_ids = _resolve_account_ids(account_id)


    # identifier = account_id or mock_data.ACCOUNT_ID
    # print(f"identifier: {identifier}")   # <-- debug print
    # try:
    #     resolved_ids = _resolve_account_ids(identifier)
    # except ValueError:
    #     return {
    #         "error": True,
    #         "message": f"I couldn't find an account matching '{identifier}'. "                       
    #     }
    # print(f"resolved_ids: {resolved_ids}")


    if len(resolved_ids) == 1:
        return _format(resolved_ids[0])

    return [_format(acc_id) for acc_id in resolved_ids]



def _resolve_account_ids(identifier: str) -> list[str]:
    """Resolve a user-facing identifier (real account ID or account type) to matching account ID(s)."""
    # Exact ID match -> just that one
    if identifier in mock_data.accounts:
        return [identifier]

    # Otherwise, treat it as a type and collect every match
    matches = [
        acc_id for acc_id, acc in mock_data.accounts.items()
        if acc.get("type", "").lower() == identifier.lower()
    ]

    if not matches:
        raise ValueError(f"No account found for '{identifier}'")

    return matches

def get_all_balances(account_id: str | list[str] | None = None) -> dict[str, Any] | list[dict[str, Any]]:
    """
    Return balance info for the given accounts, or all accounts if none specified.

    - No argument: returns all accounts.
    - Single account_id (str): returns that one account's info as a dict.
    - List of account_ids: returns a list of dicts, one per account.
    """

    def _format(acc_id: str) -> dict[str, Any]:
        account = mock_data.accounts[acc_id]
        return {
            "account": acc_id,
            "balance": account["balance"],
            "status": account["status"],
            "daily_limit": account["daily_limit"],
            "daily_used": account["daily_used"],
        }

    # No argument -> return all accounts
    if account_id is None:
        return [_format(acc_id) for acc_id in mock_data.accounts]

    # List of account IDs -> return a list
    if isinstance(account_id, list):
        return [_format(acc_id) for acc_id in account_id]

    # Single account ID -> return a single dict
    return _format(account_id)


def _resolve_account_id(identifier: str) -> str:
    """Resolve a user-facing identifier (account ID or account type) to a real account ID."""
    # Exact ID match
    if identifier in mock_data.accounts:
        return identifier

    # Match by type (e.g. "checking", "savings")
    matches = [
        acc_id for acc_id, acc in mock_data.accounts.items()
        if acc.get("type", "").lower() == identifier.lower()
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(f"Multiple accounts match '{identifier}': {matches}")

    raise ValueError(f"No account found for '{identifier}'")


def find_beneficiaries(query: str) -> dict[str, Any]:
    """Search beneficiaries by name, id, or last-4 account digits."""
    matches = mock_data.resolve_beneficiaries(query)
    return {"query": query, "matches": [mock_data.public_beneficiary(b) for b in matches]}


def initiate_transfer(beneficiary: str, amount: float,account_id: str | None = None,) -> dict[str, Any]:
    """Validate a transfer request and stage it for confirmation. Does not move money.

    Args:
        beneficiary: Pass the user's reference to the beneficiary EXACTLY as
            they gave it (e.g. "john", "John", "John S."). Do NOT guess,
            autocomplete, or resolve this to a specific full name yourself —
            this function performs beneficiary matching and will return
            NEEDS_CLARIFICATION with candidates if the reference is
            ambiguous. Passing an already-guessed full name defeats this
            safety check.
        amount: Amount to transfer.
        account_id: Source account — a real account ID or a type like
            "savings"/"checking". If omitted and the user has multiple
            accounts, this function will ask for clarification.
    

    The request is validated by PolicyService first. Possible outcomes:
    - NEEDS_CLARIFICATION: More than one match was found for either the
      beneficiary or the source account (e.g. the user has multiple accounts
      and didn't specify which one to transfer from). Nothing staged; ask
      the user to clarify which beneficiary and/or account they mean.
    - REJECTED: a deterministic rule failed (blocked beneficiary, amount,
      balance, or daily limit); nothing staged.
    - PENDING_CONFIRMATION: the request is valid and now staged. Tell the
      user the beneficiary, masked account, and amount, and ask them to
      confirm before calling confirm_transfer.
    - BLOCKED: a session limit (too many transfer attempts, or the same
      failing request repeated too many times) was reached; nothing staged.
    """

    # --- 1. Resolve the source account ---
    if account_id is None:
        # No account specified — check how many accounts the user actually has
        all_account_ids = list(mock_data.accounts.keys())

        if len(all_account_ids) > 1:
            return {
                "status": "NEEDS_CLARIFICATION",
                "message": "You have multiple accounts. Which account would you like to transfer from?",
                "candidates": [
                    {"account": acc_id, "type": mock_data.accounts[acc_id].get("type", "unknown")}
                    for acc_id in all_account_ids
                ],
            }

        # Only one account exists -> safe to default to it
        resolved_account_ids = all_account_ids

    else:
        try:
            resolved_account_ids = _resolve_account_ids(account_id)
        except ValueError:
            return {
                "status": "REJECTED",
                "message": f"No account found matching '{account_id}'.",
            }

        if len(resolved_account_ids) > 1:
            return {
                "status": "NEEDS_CLARIFICATION",
                "message": f"You have multiple accounts matching '{account_id}'. Please specify which one to transfer from.",
                "candidates": [
                    {"account": acc_id, "type": mock_data.accounts[acc_id].get("type", "unknown")}
                    for acc_id in resolved_account_ids
                ],
            }

    source_account_id = resolved_account_ids[0]

# --- 2. Resolve the beneficiary ---
    print(f"Initiating transfer to beneficiary '{beneficiary}' for amount {amount} from account '{source_account_id}'")  # <-- debug print
    result = find_beneficiaries(beneficiary)
    print(f"find_beneficiaries result: {result}")  # <-- debug print
    matches = result["matches"]
    print(f"Resolved beneficiaries: {matches}")  # <-- debug print
    resolved_beneficiary = matches[0]
    print(f"Resolved beneficiary: {resolved_beneficiary}")  # <-- debug print

    if len(matches) == 0:
        return {"status": "REJECTED", "message": f"No active beneficiary found matching '{beneficiary}'."}

    if len(matches) > 1:
        return {
            "status": "NEEDS_CLARIFICATION",
            "message": f"Multiple beneficiaries match '{beneficiary}'. Please specify which one.",
            "candidates": matches,
        }

    resolved_beneficiary = matches[0]

    validation = policy_service.validate_transfer(resolved_beneficiary, amount, source_account_id)

    if validation.status == "REJECTED":
        within_limit = limits.record_transfer_outcome(is_rejection=True, signature=validation.reason)
        audit.log("VALIDATION_FAILED", outcome="REJECTED", reason=validation.reason)
        if not within_limit:
            audit.log("LIMIT_EXCEEDED", limit="MAX_IDENTICAL_FAILURES", reason=validation.reason)
            return {
                "status": "BLOCKED",
                "reason": f"Repeated the same failing request too many times ({validation.reason}).",
            }
        return {"status": "REJECTED", "reason": validation.reason}

    limits.record_transfer_outcome(is_rejection=False)
    audit.log("VALIDATION_PASSED", beneficiary=validation.beneficiary["name"], amount=amount)

    target = validation.beneficiary
    # account_last4 = mock_data.mask_account_number(target["account_number"])
    account_last4 = target["account_last4"]   # already masked by public_beneficiary
    transfer_service.set_pending(
        transfer_service.PendingTransfer(
            beneficiary_id=target["id"],
            beneficiary_name=target["name"],
            account_last4=account_last4,
            amount=amount,
            account_id=source_account_id,
        )
    )

    audit.log("CONFIRMATION_REQUESTED", beneficiary=target["name"], account_last4=account_last4, amount=amount)
    return {
        "status": "PENDING_CONFIRMATION",
        "beneficiary_name": target["name"],
        "account_last4": account_last4,
        "amount": amount,
    }


def confirm_transfer() -> dict[str, Any]:
    """Execute the currently staged transfer, if one exists. Takes no parameters.

    This only executes a transfer that was actually staged by a prior
    initiate_transfer call. If nothing is staged it is a no-op, regardless
    of what the user or model asked for.

    The returned status (SUCCESS, FAILED, or PENDING) is the verified
    outcome from transaction_executor, not an assumption that calling this
    function without an exception means the transfer succeeded. Report this
    status to the user exactly as returned — do not assume success.
    """
    pending = transfer_service.get_pending()
    if pending is None:
        return {
            "status": "NO_PENDING_TRANSFER",
            "reason": "There is no pending transfer to confirm.",
        }
    transfer_service.clear_pending()
    audit.log("TRANSFER_CONFIRMED", beneficiary=pending.beneficiary_name, amount=pending.amount)

    outcome = transaction_executor.execute()

    account = mock_data.accounts[pending.account_id]
    if outcome in ("SUCCESS", "PENDING"):
        # A pending transfer still places a hold on the funds; a failed one
        # never leaves the account.
        account["balance"] -= pending.amount
        account["daily_used"] += pending.amount

    transaction_id = mock_data.next_transaction_id()
    mock_data.transactions[transaction_id] = {
        "id": transaction_id,
        "beneficiary_id": pending.beneficiary_id,
        "beneficiary_name": pending.beneficiary_name,
        "amount": pending.amount,
        "status": outcome,
    }
    audit.log("TRANSFER_EXECUTED", transaction_id=transaction_id, outcome=outcome)

    result = {
        "status": outcome,
        "transaction_id": transaction_id,
        "beneficiary_name": pending.beneficiary_name,
        "amount": pending.amount,
    }
    if outcome != "FAILED":
        result["new_balance"] = account["balance"]
    audit.log("TRANSACTION_VERIFIED", transaction_id=transaction_id, status=outcome)
    return result


def get_transaction_status(transaction_id: str) -> dict[str, Any]:
    """Look up the status of a previously executed transfer by transaction id."""
    transaction = mock_data.transactions.get(transaction_id)
    if transaction is None:
        return {"status": "ERROR", "reason": f"No transaction found with id '{transaction_id}'."}
    return transaction
