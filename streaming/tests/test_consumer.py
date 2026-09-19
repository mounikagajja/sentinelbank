from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from backend.app.models import Account, Customer, FraudFlag, Transaction
from streaming.consumer.score import load_model, score_message, write_flag
from streaming.producer.produce import to_message

BASE = datetime(2026, 9, 1, 3, 0, tzinfo=UTC)


@pytest.fixture
def account_with_history(db):
    customer = Customer(
        full_name="Consumer Test",
        email="consumer@example.com",
        home_city="Tempe",
        home_country="US",
    )
    account = Account(customer=customer, account_type="checking")
    history = [
        Transaction(
            account=account,
            amount=45.0,
            transaction_type="purchase",
            channel="pos",
            merchant_name="Safeway",
            merchant_category="grocery",
            city="Tempe",
            country="US",
            occurred_at=BASE - timedelta(days=d),
        )
        for d in range(10, 0, -1)
    ]
    db.add(customer)
    db.flush()
    return account, history


def add_transaction(db, account: Account, **overrides) -> Transaction:
    defaults = {
        "amount": 40.0,
        "transaction_type": "purchase",
        "channel": "pos",
        "merchant_name": "Safeway",
        "merchant_category": "grocery",
        "city": "Tempe",
        "country": "US",
        "occurred_at": BASE,
    }
    txn = Transaction(account_id=account.id, **{**defaults, **overrides})
    db.add(txn)
    db.flush()
    return txn


def test_producer_message_round_trips(db, account_with_history):
    account, _ = account_with_history
    txn = add_transaction(db, account)
    payload = to_message(txn)
    assert payload["transaction_id"] == txn.id
    assert payload["amount"] == pytest.approx(40.0)
    assert datetime.fromisoformat(payload["occurred_at"]) == txn.occurred_at


def test_obvious_fraud_scores_higher_than_routine_purchase(db, account_with_history):
    account, _ = account_with_history
    model = load_model()

    routine = add_transaction(db, account)
    routine_score, _ = score_message(db, model, to_message(routine))

    suspicious = add_transaction(
        db,
        account,
        amount=1900.0,
        channel="online",
        merchant_name="Newegg",
        merchant_category="electronics",
        occurred_at=BASE + timedelta(minutes=5),
    )
    suspicious_score, _ = score_message(db, model, to_message(suspicious))

    assert 0.0 <= routine_score <= 1.0
    assert suspicious_score > routine_score


def test_write_flag_is_idempotent(db, account_with_history):
    account, _ = account_with_history
    txn = add_transaction(db, account)

    assert write_flag(db, txn.id, 0.91) is True
    assert write_flag(db, txn.id, 0.91) is False

    count = db.scalar(
        select(func.count()).select_from(FraudFlag).where(FraudFlag.transaction_id == txn.id)
    )
    assert count == 1


def test_write_flag_records_score_and_version(db, account_with_history):
    account, _ = account_with_history
    txn = add_transaction(db, account)
    write_flag(db, txn.id, 0.83)

    flag = db.scalar(select(FraudFlag).where(FraudFlag.transaction_id == txn.id))
    assert flag.fraud_score == pytest.approx(0.83)
    assert flag.model_version == "xgb-v1"
    assert flag.status == "open"
