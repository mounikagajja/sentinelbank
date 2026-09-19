from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from backend.app.models import Account, Customer, Transaction
from ml.features.build import FEATURE_COLUMNS, build_features
from ml.features.online import compute_features

BASE = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)

ROWS = [
    {"minutes": 0, "amount": 100.0, "merchant_category": "grocery", "country": "US"},
    {"minutes": 20, "amount": 50.0, "merchant_category": "grocery", "country": "US"},
    {"minutes": 90, "amount": 400.0, "merchant_category": "electronics", "country": "US"},
    {"minutes": 200, "amount": 250.0, "merchant_category": "retail", "country": "GB"},
]


@pytest.fixture
def seeded(db):
    customer = Customer(
        full_name="Skew Test", email="skew@example.com", home_city="Tempe", home_country="US"
    )
    account = Account(customer=customer, account_type="checking")
    txns = [
        Transaction(
            account=account,
            amount=row["amount"],
            transaction_type="purchase",
            channel="pos",
            merchant_name="Store",
            merchant_category=row["merchant_category"],
            city="Tempe",
            country=row["country"],
            occurred_at=BASE + timedelta(minutes=row["minutes"]),
        )
        for row in ROWS
    ]
    db.add(customer)
    db.flush()
    return account, txns


def batch_frame(account_id: int) -> pd.DataFrame:
    records = [
        {
            "id": i + 1,
            "account_id": account_id,
            "amount": row["amount"],
            "transaction_type": "purchase",
            "channel": "pos",
            "merchant_category": row["merchant_category"],
            "country": row["country"],
            "home_country": "US",
            "occurred_at": BASE + timedelta(minutes=row["minutes"]),
            "is_fraud": False,
            "pattern": None,
        }
        for i, row in enumerate(ROWS)
    ]
    df = pd.DataFrame(records)
    df["occurred_at"] = pd.to_datetime(df["occurred_at"], utc=True)
    return build_features(df)


def test_online_features_match_batch_features(db, seeded):
    account, txns = seeded
    batch = batch_frame(account.id)

    for position, txn in enumerate(txns):
        online = compute_features(
            db,
            transaction_id=txn.id,
            account_id=account.id,
            amount=float(txn.amount),
            transaction_type=txn.transaction_type,
            channel=txn.channel,
            merchant_category=txn.merchant_category,
            country=txn.country,
            home_country="US",
            occurred_at=txn.occurred_at,
        )
        expected = batch.iloc[position]
        for name in FEATURE_COLUMNS:
            assert online[name] == pytest.approx(float(expected[name]), rel=1e-6), (
                f"row {position}, feature {name}: online {online[name]} vs batch {expected[name]}"
            )
