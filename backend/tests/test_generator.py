import random
from datetime import UTC, datetime

from backend.app.models import Account
from data.generator.generate import (
    atm_drain,
    card_testing,
    impossible_travel,
    night_high_value,
    normal_transaction,
)

HOME = ("Tempe", "US")
DAY = datetime(2026, 9, 1, tzinfo=UTC)


def make_account() -> Account:
    account = Account(customer_id=1, account_type="checking")
    account.id = 1
    return account


def test_normal_transaction_is_not_fraud_and_at_home():
    txn = normal_transaction(make_account(), DAY, HOME, random.Random(1))
    assert txn.is_fraud is False
    assert (txn.city, txn.country) == HOME
    assert txn.amount > 0


def test_card_testing_is_a_burst_of_tiny_online_purchases():
    txns = card_testing(make_account(), DAY, HOME, random.Random(2))
    assert 5 <= len(txns) <= 8
    assert all(t.is_fraud and t.channel == "online" and t.amount <= 3 for t in txns)
    offsets = [(t.occurred_at - txns[0].occurred_at).total_seconds() for t in txns]
    assert max(offsets) < 15 * 60


def test_impossible_travel_changes_country_within_90_minutes():
    home_txn, far_txn = impossible_travel(make_account(), DAY, HOME, random.Random(3))
    assert home_txn.is_fraud is False
    assert far_txn.is_fraud is True
    assert far_txn.country != home_txn.country
    gap = (far_txn.occurred_at - home_txn.occurred_at).total_seconds()
    assert 30 * 60 <= gap <= 90 * 60


def test_night_high_value_is_large_and_in_early_hours():
    txns = night_high_value(make_account(), DAY, HOME, random.Random(4))
    assert 1 <= len(txns) <= 2
    assert all(t.is_fraud and t.amount >= 800 and 1 <= t.occurred_at.hour <= 5 for t in txns)


def test_atm_drain_is_repeated_large_withdrawals():
    txns = atm_drain(make_account(), DAY, HOME, random.Random(5))
    assert 3 <= len(txns) <= 5
    assert all(t.is_fraud and t.channel == "atm" and t.amount >= 200 for t in txns)
