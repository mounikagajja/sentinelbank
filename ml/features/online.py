from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from ml.features.build import CATEGORIES, CHANNELS, FEATURE_COLUMNS, TYPES

HISTORY_SQL = text("""
    WITH prior AS (
        SELECT t.amount, t.merchant_category, t.country, t.occurred_at,
               EXTRACT(HOUR FROM t.occurred_at AT TIME ZONE 'UTC') AS hour
        FROM transactions t
        WHERE t.account_id = :account_id
          AND (t.occurred_at < :occurred_at
               OR (t.occurred_at = :occurred_at AND t.id < :transaction_id))
    )
    SELECT
        (SELECT COUNT(*) FROM prior) AS prior_rows,
        (SELECT COUNT(*) FROM prior WHERE occurred_at > :occurred_at - INTERVAL '1 hour') AS count_1h,
        (SELECT COALESCE(SUM(amount), 0) FROM prior WHERE occurred_at > :occurred_at - INTERVAL '1 hour') AS sum_1h,
        (SELECT COUNT(*) FROM prior WHERE occurred_at > :occurred_at - INTERVAL '24 hours') AS count_24h,
        (SELECT COALESCE(SUM(amount), 0) FROM prior WHERE occurred_at > :occurred_at - INTERVAL '24 hours') AS sum_24h,
        (SELECT MAX(occurred_at) FROM prior) AS prev_at,
        (SELECT country FROM prior ORDER BY occurred_at DESC, amount DESC LIMIT 1) AS prev_country,
        (SELECT MIN(occurred_at) FROM prior) AS first_at,
        (SELECT AVG(amount) FROM prior) AS prev_mean,
        (SELECT COUNT(*) FROM prior WHERE merchant_category = :merchant_category) AS prior_same_category,
        (SELECT AVG(amount) FROM prior WHERE merchant_category = :merchant_category) AS category_prev_mean,
        (SELECT COUNT(*) FROM prior WHERE hour = :hour) AS prior_same_hour
""")

NO_HISTORY_SECONDS = 30 * 24 * 3600


def compute_features(
    db: Session,
    transaction_id: int,
    account_id: int,
    amount: float,
    transaction_type: str,
    channel: str,
    merchant_category: str,
    country: str,
    home_country: str,
    occurred_at: datetime,
) -> dict[str, float]:
    hour = occurred_at.hour
    row = (
        db.execute(
            HISTORY_SQL,
            {
                "account_id": account_id,
                "occurred_at": occurred_at,
                "transaction_id": transaction_id,
                "merchant_category": merchant_category,
                "hour": hour,
            },
        )
        .mappings()
        .one()
    )

    prior_rows = int(row["prior_rows"])

    if row["prev_at"] is None:
        secs_since_prev = float(NO_HISTORY_SECONDS)
        country_changed = 0
    else:
        secs_since_prev = (occurred_at - row["prev_at"]).total_seconds()
        country_changed = int(country != row["prev_country"])

    prev_mean = float(row["prev_mean"]) if row["prev_mean"] else None
    category_prev_mean = float(row["category_prev_mean"]) if row["category_prev_mean"] else None

    if row["first_at"] is None:
        days_elapsed = 1
    else:
        days_elapsed = (occurred_at - row["first_at"]).days + 1
    daily_avg = prior_rows / days_elapsed if days_elapsed else 0.0
    count_24h = float(row["count_24h"]) + 1.0

    features = {
        "amount": float(amount),
        "hour": float(hour),
        "day_of_week": float(occurred_at.weekday()),
        "is_night": float(0 <= hour <= 5),
        "is_weekend": float(occurred_at.weekday() >= 5),
        "channel_code": float(CHANNELS.index(channel)) if channel in CHANNELS else -1.0,
        "category_code": float(CATEGORIES.index(merchant_category))
        if merchant_category in CATEGORIES
        else -1.0,
        "type_code": float(TYPES.index(transaction_type)) if transaction_type in TYPES else -1.0,
        "is_foreign": float(country != home_country),
        "secs_since_prev": secs_since_prev,
        "country_changed": float(country_changed),
        "count_1h": float(row["count_1h"]) + 1.0,
        "sum_1h": float(row["sum_1h"]) + float(amount),
        "count_24h": count_24h,
        "sum_24h": float(row["sum_24h"]) + float(amount),
        "amount_vs_prev_mean": float(amount) / prev_mean if prev_mean else 1.0,
        "hour_is_unusual": float(int(row["prior_same_hour"]) == 0),
        "count_24h_vs_daily_avg": count_24h / daily_avg if daily_avg else 1.0,
        "category_share_prev": int(row["prior_same_category"]) / prior_rows if prior_rows else 0.0,
        "amount_vs_category_mean": float(amount) / category_prev_mean
        if category_prev_mean
        else 1.0,
    }
    return {name: features[name] for name in FEATURE_COLUMNS}
