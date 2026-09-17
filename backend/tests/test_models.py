from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from backend.app.models import Account, Customer, FraudFlag, Transaction


def build_chain() -> tuple[Customer, Account, Transaction]:
    customer = Customer(
        full_name="Test User", email="test-chain@example.com", home_city="Tempe", home_country="US"
    )
    account = Account(customer=customer, account_type="checking", balance=Decimal("100.00"))
    txn = Transaction(
        account=account,
        amount=Decimal("0.10"),
        transaction_type="purchase",
        channel="pos",
        merchant_name="Target",
        merchant_category="retail",
        city="Tempe",
        country="US",
        occurred_at=datetime.now(UTC),
    )
    return customer, account, txn


def test_relationships_fill_foreign_keys(db):
    customer, account, txn = build_chain()
    db.add(customer)
    db.flush()
    assert customer.id is not None
    assert account.customer_id == customer.id
    assert txn.account_id == account.id


def test_defaults_are_applied(db):
    customer, account, txn = build_chain()
    db.add(customer)
    db.flush()
    db.refresh(account)
    assert account.status == "active"
    assert txn.is_fraud is False
    assert account.created_at is not None


def test_money_is_stored_exactly(db):
    customer, account, txn = build_chain()
    db.add(customer)
    db.flush()
    db.refresh(txn)
    assert txn.amount == Decimal("0.10")


def test_one_fraud_flag_per_transaction(db):
    customer, account, txn = build_chain()
    db.add(customer)
    db.flush()
    db.add(FraudFlag(transaction=txn, fraud_score=0.9, model_version="test"))
    db.flush()
    db.add(FraudFlag(transaction_id=txn.id, fraud_score=0.8, model_version="test"))
    with pytest.raises(IntegrityError):
        db.flush()
