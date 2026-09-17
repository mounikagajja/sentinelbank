import random
from datetime import UTC, datetime

from backend.app.models import Account
from data.generator.generate import (
    atm_drain,
    card_testing,
    impossible_travel,
    make_profile,
    night_high_value,
    normal_transaction,
    subtle_takeover,
)

HOME = ("Tempe", "US")
DAY = datetime(2026, 9, 1, tzinfo=UTC)


def make_account() -> Account:
    account = Account(customer_id=1, account_type="checking")
    account.id = 1
    return account


def profile(seed: int) -> dict:
    return make_profile(HOME, random.Random(seed))


def test_normal_transaction_is_not_fraud_and_unlabeled():
    txn = normal_transaction(make_account(), DAY, profile(1), random.Random(1))
    assert txn.is_fraud is False
    assert txn.pattern is None
    assert (txn.city, txn.country) == HOME
    assert txn.amount > 0


def test_card_testing_is_small_online_charges_within_an_hour():
    txns = card_testing(make_account(), DAY, profile(2), random.Random(2))
    assert 3 <= len(txns) <= 8
    assert all(t.is_fraud and t.pattern == "card_testing" and t.channel == "online" for t in txns)
    assert all(t.amount <= 15 for t in txns)
    offsets = [(t.occurred_at - txns[0].occurred_at).total_seconds() for t in txns]
    assert max(offsets) <= 70 * 60


def test_impossible_travel_changes_city_within_two_hours():
    home_txn, far_txn = impossible_travel(make_account(), DAY, profile(3), random.Random(3))
    assert home_txn.is_fraud is False
    assert far_txn.is_fraud is True and far_txn.pattern == "impossible_travel"
    assert far_txn.city != home_txn.city
    gap = (far_txn.occurred_at - home_txn.occurred_at).total_seconds()
    assert 30 * 60 <= gap <= 120 * 60


def test_night_high_value_is_large_and_in_early_hours():
    txns = night_high_value(make_account(), DAY, profile(4), random.Random(4))
    assert 1 <= len(txns) <= 2
    assert all(t.is_fraud and t.pattern == "night_high_value" for t in txns)
    assert all(t.amount >= 800 and 1 <= t.occurred_at.hour <= 5 for t in txns)


def test_atm_drain_is_repeated_large_withdrawals():
    txns = atm_drain(make_account(), DAY, profile(5), random.Random(5))
    assert 3 <= len(txns) <= 5
    assert all(t.is_fraud and t.pattern == "atm_drain" and t.channel == "atm" for t in txns)
    assert all(t.amount >= 200 for t in txns)


def test_subtle_takeover_uses_an_unusual_category_at_home():
    p = profile(6)
    txns = subtle_takeover(make_account(), DAY, p, random.Random(6))
    assert 1 <= len(txns) <= 2
    assert all(t.is_fraud and t.pattern == "subtle_takeover" for t in txns)
    assert all(t.merchant_category not in p["favorites"] for t in txns)
    assert all((t.city, t.country) == HOME for t in txns)
