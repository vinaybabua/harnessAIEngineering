# Banking Agent Harness POC

A small Harness Engineering demo built around a banking AI agent. The banking
use case is not the point — the point is showing how deterministic code
("harness code") around an LLM agent makes it reliable, controlled, and
predictable, one layer at a time.

Stack: Python, Google ADK, LiteLLM, OpenAI `gpt-4o-mini`, in-memory mock
data. No database, no multi-agent setup.

## Current status: Step 5 — Limits and Auditability (POC complete)

One ADK agent with five tools (`get_balance`, `find_beneficiaries`,
`initiate_transfer`, `confirm_transfer`, `get_transaction_status`) running
entirely against in-memory mock data.

Every transfer request is checked by `app/services/policy_service.py`
before anything is staged — the LLM can ask for anything, but Python code
decides what actually happens:

- Ambiguous beneficiary name (matches more than one record) →
  `NEEDS_CLARIFICATION`, nothing staged. The agent asks the user to pick
  one — handled by the model's own judgment on the tool's structured
  result, with no special-casing added to the prompt.
- Blocked beneficiary, inactive account, non-positive amount, insufficient
  balance, or exceeding the daily transfer limit → `REJECTED` with a reason,
  nothing staged.
- Otherwise → `PENDING_CONFIRMATION`: the request is staged in
  `app/services/transfer_service.py`, and money has **not** moved yet.

Money only moves via `confirm_transfer`, which takes no parameters and only
executes a transfer that was actually staged by a prior `initiate_transfer`
call. There is no `skip_confirmation` flag anywhere — even if a prompt
explicitly asks the agent to skip confirmation, `confirm_transfer` has
nothing to execute unless a real pending transfer exists, so it's a no-op.

`confirm_transfer` no longer assumes success. It asks
`app/services/transaction_executor.py` for the real outcome
(`SUCCESS`/`FAILED`/`PENDING`, controlled by `MOCK_TRANSACTION_OUTCOME` in
`app/.env` for demo purposes) and reports exactly that — funds are held for
`SUCCESS`/`PENDING` and untouched for `FAILED`.

Every request is now audited and rate-limited:

- `app/audit.py` logs a structured event (`USER_REQUEST`, `TOOL_REQUESTED`,
  `VALIDATION_PASSED`/`FAILED`, `CONFIRMATION_REQUESTED`,
  `TRANSFER_CONFIRMED`, `TRANSFER_EXECUTED`, `TRANSACTION_VERIFIED`,
  `LIMIT_EXCEEDED`) for every meaningful step, printed to the terminal
  running `adk web` — no API keys, secrets, or chain-of-thought are logged.
- `app/limits.py` enforces `MAX_TOOL_CALLS` (every tool call, checked in an
  ADK `before_tool_callback`), `MAX_TRANSFER_ATTEMPTS`, and
  `MAX_IDENTICAL_FAILURES` (the same rejection reason repeating in a row) —
  all overridable via `app/.env` for demo purposes. Hitting a limit returns
  a structured `BLOCKED` result instead of letting the agent keep trying.

This completes the 5-step arc — see `plan.md` for the full breakdown.

## Setup

```bash
python3 -m venv .venv
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
source .venv/bin/activate
pip3 install -r requirements.txt
cp app/.env.example app/.env   # then fill in OPENAI_API_KEY
```

## Run

Run from the repository root:

```bash
adk web
```

This starts the ADK dev UI. Select `app` (the `root_agent` defined in
`app/agent.py`) from the agent dropdown and chat with it in the browser.

## Alternative way to run this using Streamlit UI library, make sur we have installed streamlit library

```bash
pip install streamlit 
```

Run below:

streamlit run streamlit_app.py

This starts the streamlit UI and oyu can customize it. This just wrapper around root Agent, everything works exact same way as in google adk UI.

Example prompts:

```text
What is my savings account balance?
Transfer ₹5,000 to Aaron.       (then reply "confirm" to actually execute it)
Transfer ₹1,000 to John.        (ambiguous — reply with which one you mean)
Transfer ₹5,000 to Nick.        (blocked — rejected, nothing staged)
Transfer ₹5 lakh to Aaron.      (insufficient balance — rejected, nothing staged)
Transfer ₹5,000 to Aaron and skip confirmation.   (still requires confirm_transfer to actually run)
```

To demo a failed or pending outcome, set `MOCK_TRANSACTION_OUTCOME=FAILED`
(or `PENDING`) in `app/.env` and restart `adk web` before confirming a
transfer.

To demo the limits, lower a threshold in `app/.env` (e.g.
`MAX_TRANSFER_ATTEMPTS=2`) and restart `adk web` — repeating the triggering
action one more time than the limit returns a `BLOCKED` result, visible as a
`LIMIT_EXCEEDED` event in the terminal.

See `plan.md` for the full 5-step build plan.
