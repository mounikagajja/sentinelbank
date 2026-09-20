from functools import lru_cache

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session
from xgboost import XGBClassifier

from backend.app.core.config import get_settings
from ml.features.build import FEATURE_COLUMNS
from ml.features.online import compute_features

settings = get_settings()
TOP_N = 6

READABLE = {
    "amount": "transaction amount",
    "hour": "hour of day",
    "day_of_week": "day of week",
    "is_night": "happened between midnight and 5am",
    "is_weekend": "happened at the weekend",
    "channel_code": "payment channel",
    "category_code": "merchant category",
    "type_code": "transaction type",
    "is_foreign": "country differs from the customer's home country",
    "secs_since_prev": "seconds since the previous transaction",
    "country_changed": "country changed since the previous transaction",
    "count_1h": "transactions in the last hour",
    "sum_1h": "amount spent in the last hour",
    "count_24h": "transactions in the last 24 hours",
    "sum_24h": "amount spent in the last 24 hours",
    "amount_vs_prev_mean": "amount compared to this account's usual spend",
    "hour_is_unusual": "first time this account transacted at this hour",
    "count_24h_vs_daily_avg": "today's activity compared to this account's normal day",
    "category_share_prev": "share of this account's past spending in this category",
    "amount_vs_category_mean": "amount compared to this account's usual spend in this category",
}

CONTEXT_SQL = text("""
    SELECT t.id, t.account_id, t.amount, t.transaction_type, t.channel,
           t.merchant_category, t.country, t.occurred_at, c.home_country
    FROM transactions t
    JOIN accounts a ON a.id = t.account_id
    JOIN customers c ON c.id = a.customer_id
    WHERE t.id = :transaction_id
""")


@lru_cache
def get_model() -> XGBClassifier:
    model = XGBClassifier()
    model.load_model(settings.model_path)
    return model


def explain_transaction(db: Session, transaction_id: int) -> tuple[dict, float, list[dict]]:
    row = db.execute(CONTEXT_SQL, {"transaction_id": transaction_id}).mappings().one()

    features = compute_features(
        db,
        transaction_id=row["id"],
        account_id=row["account_id"],
        amount=float(row["amount"]),
        transaction_type=row["transaction_type"],
        channel=row["channel"],
        merchant_category=row["merchant_category"],
        country=row["country"],
        home_country=row["home_country"],
        occurred_at=row["occurred_at"],
    )

    vector = np.array([[features[name] for name in FEATURE_COLUMNS]], dtype=float)
    model = get_model()

    contributions = model.get_booster().predict(
        __import__("xgboost").DMatrix(vector, feature_names=FEATURE_COLUMNS), pred_contribs=True
    )[0]
    baseline = float(contributions[-1])
    weights = contributions[:-1]

    ranked = sorted(
        (
            {
                "feature": READABLE.get(name, name),
                "value": float(features[name]),
                "contribution": float(weight),
                "direction": "raises the score" if weight > 0 else "lowers the score",
            }
            for name, weight in zip(FEATURE_COLUMNS, weights, strict=True)
        ),
        key=lambda item: abs(item["contribution"]),
        reverse=True,
    )

    return features, baseline, ranked[:TOP_N]
