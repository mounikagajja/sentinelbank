from datetime import UTC, datetime, timedelta

import pandas as pd

from ml.features.build import FEATURE_COLUMNS, build_features

BASE = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def frame(rows: list[dict]) -> pd.DataFrame:
    defaults = {
        "account_id": 1,
        "amount": 50.0,
        "transaction_type": "purchase",
        "channel": "pos",
        "merchant_category": "grocery",
        "country": "US",
        "home_country": "US",
        "is_fraud": False,
        "pattern": None,
    }
    records = []
    for i, row in enumerate(rows):
        record = {**defaults, "id": i + 1, "occurred_at": BASE, **row}
        records.append(record)
    df = pd.DataFrame(records)
    df["occurred_at"] = pd.to_datetime(df["occurred_at"], utc=True)
    return df


def test_output_has_every_feature_column():
    out = build_features(frame([{}]))
    assert all(col in out.columns for col in FEATURE_COLUMNS)


def test_windows_only_look_backward():
    out = build_features(
        frame(
            [
                {"occurred_at": BASE, "amount": 10.0},
                {"occurred_at": BASE + timedelta(minutes=30), "amount": 20.0},
                {"occurred_at": BASE + timedelta(hours=2), "amount": 30.0},
            ]
        )
    )
    assert out["count_1h"].tolist() == [1, 2, 1]
    assert out["sum_1h"].tolist() == [10.0, 30.0, 30.0]
    assert out["count_24h"].tolist() == [1, 2, 3]


def test_windows_do_not_cross_accounts():
    out = build_features(
        frame(
            [
                {"account_id": 1, "occurred_at": BASE},
                {"account_id": 2, "occurred_at": BASE + timedelta(minutes=5)},
            ]
        )
    )
    assert out["count_1h"].tolist() == [1, 1]


def test_secs_since_prev_and_country_change():
    out = build_features(
        frame(
            [
                {"occurred_at": BASE, "country": "US"},
                {"occurred_at": BASE + timedelta(minutes=45), "country": "GB"},
            ]
        )
    )
    assert out["secs_since_prev"].iloc[0] == 30 * 24 * 3600
    assert out["secs_since_prev"].iloc[1] == 45 * 60
    assert out["country_changed"].tolist() == [0, 1]
    assert out["is_foreign"].tolist() == [0, 1]


def test_amount_ratios_use_previous_rows_only():
    out = build_features(
        frame(
            [
                {"occurred_at": BASE, "amount": 100.0},
                {"occurred_at": BASE + timedelta(days=1), "amount": 100.0},
                {"occurred_at": BASE + timedelta(days=2), "amount": 400.0},
            ]
        )
    )
    assert out["amount_vs_prev_mean"].tolist() == [1.0, 1.0, 4.0]
    assert out["amount_vs_category_mean"].tolist() == [1.0, 1.0, 4.0]


def test_category_share_is_fraction_of_prior_rows():
    out = build_features(
        frame(
            [
                {"occurred_at": BASE, "merchant_category": "grocery"},
                {"occurred_at": BASE + timedelta(days=1), "merchant_category": "grocery"},
                {"occurred_at": BASE + timedelta(days=2), "merchant_category": "grocery"},
                {"occurred_at": BASE + timedelta(days=3), "merchant_category": "electronics"},
            ]
        )
    )
    assert out["category_share_prev"].tolist() == [0.0, 1.0, 1.0, 0.0]


def test_unknown_codes_become_minus_one():
    out = build_features(frame([{"channel": "carrier_pigeon", "merchant_category": "unknown"}]))
    assert out["channel_code"].iloc[0] == -1
    assert out["category_code"].iloc[0] == -1
