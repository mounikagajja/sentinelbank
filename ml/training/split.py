import pandas as pd


def time_split(df: pd.DataFrame, test_days: int = 15) -> tuple[pd.DataFrame, pd.DataFrame]:
    cutoff = df["occurred_at"].max().normalize() - pd.Timedelta(days=test_days)
    train = df[df["occurred_at"] < cutoff]
    test = df[df["occurred_at"] >= cutoff]
    return train, test
