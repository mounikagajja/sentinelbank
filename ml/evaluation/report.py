from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, confusion_matrix, roc_auc_score
from xgboost import XGBClassifier

from ml.features.build import FEATURE_COLUMNS, TARGET
from ml.training.split import time_split

MODEL_PATH = Path("models/fraud_xgb.json")
REPORT_PATH = Path("docs/evaluation.md")
THRESHOLDS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]


def threshold_sweep(y: pd.Series, proba: np.ndarray) -> pd.DataFrame:
    rows = []
    for t in THRESHOLDS:
        pred = (proba >= t).astype(int)
        tp = int(((pred == 1) & (y == 1)).sum())
        fp = int(((pred == 1) & (y == 0)).sum())
        fn = int(((pred == 0) & (y == 1)).sum())
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        rows.append(
            {"threshold": t, "flagged": tp + fp, "precision": precision, "recall": recall, "f1": f1}
        )
    return pd.DataFrame(rows)


def per_pattern_recall(test: pd.DataFrame, proba: np.ndarray, threshold: float) -> pd.DataFrame:
    frame = test[[TARGET, "pattern"]].copy()
    frame["caught"] = (proba >= threshold).astype(int)
    fraud = frame[frame[TARGET] == 1]
    grouped = fraud.groupby("pattern")["caught"].agg(["count", "sum"])
    grouped["recall"] = grouped["sum"] / grouped["count"]
    return grouped.rename(columns={"count": "fraud_rows", "sum": "caught"})


def main() -> None:
    df = pd.read_parquet("data/processed/features.parquet")
    train, test = time_split(df)
    y_test = test[TARGET]

    model = XGBClassifier()
    model.load_model(MODEL_PATH)
    proba = model.predict_proba(test[FEATURE_COLUMNS])[:, 1]

    sweep = threshold_sweep(y_test, proba)
    best = sweep.loc[sweep["f1"].idxmax()]
    chosen = float(best["threshold"])

    patterns = per_pattern_recall(test, proba, chosen)
    tn, fp, fn, tp = confusion_matrix(y_test, (proba >= chosen).astype(int)).ravel()

    lines = [
        "# Fraud model evaluation",
        "",
        f"Model: `{MODEL_PATH}`.",
        f"Test set: last 15 days, {len(test)} rows, {int(y_test.sum())} fraud.",
        "",
        f"PR-AUC: {average_precision_score(y_test, proba):.4f}",
        f"ROC-AUC: {roc_auc_score(y_test, proba):.4f}",
        "",
        "## Threshold sweep",
        "",
        sweep.round(4).to_markdown(index=False),
        "",
        f"Best F1 at threshold {chosen}.",
        "",
        f"## Confusion matrix at {chosen}",
        "",
        "| | Predicted normal | Predicted fraud |",
        "|---|---|---|",
        f"| Actual normal | {tn} | {fp} |",
        f"| Actual fraud | {fn} | {tp} |",
        "",
        f"## Recall by fraud pattern at {chosen}",
        "",
        patterns.round(4).to_markdown(),
        "",
    ]
    REPORT_PATH.parent.mkdir(exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"written: {REPORT_PATH}")


if __name__ == "__main__":
    main()
