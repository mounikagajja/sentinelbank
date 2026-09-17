from pathlib import Path

import pandas as pd
from sqlalchemy import text

from backend.app.db.session import engine

CHANNELS = ["pos", "online", "atm"]
CATEGORIES = [
    "grocery", "restaurant", "fuel", "retail", "online",
    "travel", "utilities", "electronics", "cash",
]
TYPES = ["purchase", "withdrawal", "transfer"]

FEATURE_COLUMNS = [
    "amount",
    "hour",
    "day_of_week",
    "is_night",
    "is_weekend",
    "channel_code",
    "category_code",
    "type_code",
    "is_foreign",
    "secs_since_prev",
    "country_changed",
    "count_1h",
    "sum_1h",
    "count_24h",
    "sum_24h",
    "amount_vs_prev_mean",
]
TARGET = "is_fraud"
ID_COLUMNS = ["id", "account_id", "occurred_at"]

QUERY = text("""
    SELECT t.id, t.account_id, t.amount, t.transaction_type, t.channel,
           t.merchant_category, t.country, t.occurred_at, t.is_fraud,
           c.home_country
    FROM transactions t
    JOIN accounts a ON a.id = t.account_id
    JOIN customers c ON c.id = a.customer_id
    ORDER BY t.account_id, t.occurred_at, t.id
""")


def load_transactions() -> pd.DataFrame:
    with engine.connect() as conn:
        df = pd.read_sql(QUERY, conn)
    df["amount"] = df["amount"].astype(float)
    df["occurred_at"] = pd.to_datetime(df["occurred_at"], utc=True)
    return df


def _window_stats(group: pd.DataFrame, window: str) -> pd.DataFrame:
    series = group.set_index("occurred_at")["amount"]
    rolled = series.rolling(window)
    return pd.DataFrame(
        {f"count_{window}": rolled.count().to_numpy(), f"sum_{window}": rolled.sum().to_numpy()},
        index=group.index,
    )


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["account_id", "occurred_at", "id"]).reset_index(drop=True)

    df["hour"] = df["occurred_at"].dt.hour
    df["day_of_week"] = df["occurred_at"].dt.dayofweek
    df["is_night"] = df["hour"].between(0, 5).astype(int)
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)

    df["channel_code"] = df["channel"].map({c: i for i, c in enumerate(CHANNELS)}).fillna(-1).astype(int)
    df["category_code"] = (
        df["merchant_category"].map({c: i for i, c in enumerate(CATEGORIES)}).fillna(-1).astype(int)
    )
    df["type_code"] = df["transaction_type"].map({t: i for i, t in enumerate(TYPES)}).fillna(-1).astype(int)
    df["is_foreign"] = (df["country"] != df["home_country"]).astype(int)

    by_account = df.groupby("account_id", group_keys=False)

    df["secs_since_prev"] = (
        by_account["occurred_at"].diff().dt.total_seconds().fillna(30 * 24 * 3600)
    )
    prev_country = by_account["country"].shift(1)
    df["country_changed"] = ((df["country"] != prev_country) & prev_country.notna()).astype(int)

    for window in ("1h", "24h"):
        stats = by_account.apply(_window_stats, window=window, include_groups=False)
        df[f"count_{window}"] = stats[f"count_{window}"]
        df[f"sum_{window}"] = stats[f"sum_{window}"]

    prev_mean = by_account["amount"].transform(lambda s: s.expanding().mean().shift(1))
    df["amount_vs_prev_mean"] = (df["amount"] / prev_mean).fillna(1.0)

    df[TARGET] = df[TARGET].astype(int)
    return df[ID_COLUMNS + FEATURE_COLUMNS + [TARGET]]


def main() -> None:
    raw = load_transactions()
    features = build_features(raw)
    out = Path("data/processed/features.parquet")
    out.parent.mkdir(parents=True, exist_ok=True)
    features.to_parquet(out, index=False)
    print(f"rows: {len(features)}")
    print(f"features: {len(FEATURE_COLUMNS)}")
    print(f"fraud rate: {features[TARGET].mean():.4f}")
    print(f"saved: {out}")


if __name__ == "__main__":
    main()