from typing import Annotated

from langchain_core.tools import InjectedToolArg, tool

from assistant.tools.client import ApiClient, ApiError

ACTION_TOOLS = {"freeze_account", "unfreeze_account", "review_flag"}

Client = Annotated[ApiClient, InjectedToolArg]


@tool
def get_account(account_id: int, client: Client) -> str:
    """Look up one bank account: its type, balance, and whether it is active or frozen."""
    try:
        account = client.get(f"/accounts/{account_id}")
    except ApiError as exc:
        return f"Error: {exc}"
    return (
        f"Account {account['id']} ({account['account_type']}) belongs to customer "
        f"{account['customer_id']}. Balance {account['balance']}. Status: {account['status']}."
    )


@tool
def list_recent_transactions(account_id: int, client: Client, limit: int = 10) -> str:
    """List the most recent transactions on an account, newest first. 
    
    Use to spot unusual activity.
    """
    try:
        page = client.get(f"/accounts/{account_id}/transactions", params={"limit": limit})
    except ApiError as exc:
        return f"Error: {exc}"

    if not page["items"]:
        return f"Account {account_id} has no transactions."

    lines = [f"{page['total']} transactions total, showing {len(page['items'])}:"]
    for txn in page["items"]:
        lines.append(
            f"- id {txn['id']}: {txn['amount']} at {txn['merchant_name']} "
            f"({txn['merchant_category']}, {txn['channel']}) in {txn['city']}, "
            f"{txn['country']} on {txn['occurred_at']}"
        )
    return "\n".join(lines)


@tool
def get_transaction(transaction_id: int, client: Client) -> str:
    """Look up one transaction by its id."""
    try:
        txn = client.get(f"/transactions/{transaction_id}")
    except ApiError as exc:
        return f"Error: {exc}"
    return (
        f"Transaction {txn['id']} on account {txn['account_id']}: {txn['amount']} at "
        f"{txn['merchant_name']} ({txn['merchant_category']}, {txn['channel']}) in "
        f"{txn['city']}, {txn['country']} on {txn['occurred_at']}."
    )


@tool
def list_open_flags(client: Client, min_score: float = 0.0, limit: int = 10) -> str:
    """List fraud flags that no one has reviewed yet, highest risk first."""
    try:
        page = client.get(
            "/flags", params={"status": "open", "min_score": min_score, "limit": limit}
        )
    except ApiError as exc:
        return f"Error: {exc}"

    if not page["items"]:
        return "There are no open fraud flags."

    lines = [f"{page['total']} open flags, showing {len(page['items'])}:"]
    for item in page["items"]:
        flag, txn = item["flag"], item["transaction"]
        lines.append(
            f"- flag {flag['id']} (score {flag['fraud_score']:.2f}) on transaction "
            f"{txn['id']}: {txn['amount']} at {txn['merchant_name']} in {txn['city']}, "
            f"{txn['country']} on {txn['occurred_at']}, account {txn['account_id']}"
        )
    return "\n".join(lines)


@tool
def get_flag(flag_id: int, client: Client) -> str:
    """Look up one fraud flag and the transaction it points at."""
    try:
        item = client.get(f"/flags/{flag_id}")
    except ApiError as exc:
        return f"Error: {exc}"
    flag, txn = item["flag"], item["transaction"]
    return (
        f"Flag {flag['id']} scored {flag['fraud_score']:.4f} by model {flag['model_version']}, "
        f"status {flag['status']}, raised {flag['created_at']}. Transaction {txn['id']} on "
        f"account {txn['account_id']}: {txn['amount']} at {txn['merchant_name']} "
        f"({txn['merchant_category']}, {txn['channel']}) in {txn['city']}, {txn['country']} "
        f"on {txn['occurred_at']}."
    )


@tool
def freeze_account(account_id: int, reason: str, client: Client) -> str:
    """Freeze an account so no further transactions can be made. Requires analyst approval."""
    try:
        account = client.patch(
            f"/accounts/{account_id}/status", json={"status": "frozen", "reason": reason}
        )
    except ApiError as exc:
        return f"Error: {exc}"
    return f"Account {account['id']} is now {account['status']}. Reason recorded: {reason}"


@tool
def unfreeze_account(account_id: int, reason: str, client: Client) -> str:
    """Return a frozen account to active. Requires analyst approval."""
    try:
        account = client.patch(
            f"/accounts/{account_id}/status", json={"status": "active", "reason": reason}
        )
    except ApiError as exc:
        return f"Error: {exc}"
    return f"Account {account['id']} is now {account['status']}. Reason recorded: {reason}"


@tool
def review_flag(flag_id: int, outcome: str, client: Client, note: str | None = None) -> str:
    """Close a fraud flag. outcome must be 'confirmed' (real fraud) or 'dismissed' (false alarm)."""
    if outcome not in {"confirmed", "dismissed"}:
        return "Error: outcome must be 'confirmed' or 'dismissed'"
    try:
        flag = client.patch(f"/flags/{flag_id}/status", json={"status": outcome, "note": note})
    except ApiError as exc:
        return f"Error: {exc}"
    return f"Flag {flag['id']} is now {flag['status']}, reviewed at {flag['reviewed_at']}."


READ_TOOLS = [get_account, list_recent_transactions, get_transaction, list_open_flags, get_flag]
WRITE_TOOLS = [freeze_account, unfreeze_account, review_flag]
ALL_TOOLS = READ_TOOLS + WRITE_TOOLS
TOOLS_BY_NAME = {t.name: t for t in ALL_TOOLS}
