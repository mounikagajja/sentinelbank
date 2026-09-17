from pathlib import Path

import mlflow
import mlflow.xgboost
import pandas as pd
from sklearn.metrics import average_precision_score, precision_score, recall_score, roc_auc_score
from xgboost import XGBClassifier

from ml.features.build import FEATURE_COLUMNS, TARGET
from ml.training.baseline import EXPERIMENT, TRACKING_URI
from ml.training.split import time_split

MODEL_DIR = Path("models")
THRESHOLD = 0.5


def main() -> None:
    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT)

    df = pd.read_parquet("data/processed/features.parquet")
    train, test = time_split(df)
    x_train, y_train = train[FEATURE_COLUMNS], train[TARGET]
    x_test, y_test = test[FEATURE_COLUMNS], test[TARGET]

    negatives, positives = (y_train == 0).sum(), (y_train == 1).sum()
    params = {
        "n_estimators": 400,
        "max_depth": 5,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "scale_pos_weight": float(negatives / positives),
        "eval_metric": "aucpr",
        "random_state": 42,
        "n_jobs": -1,
    }

    with mlflow.start_run(run_name="xgboost"):
        model = XGBClassifier(**params)
        model.fit(x_train, y_train, eval_set=[(x_test, y_test)], verbose=False)

        proba = model.predict_proba(x_test)[:, 1]
        predicted = (proba >= THRESHOLD).astype(int)

        metrics = {
            "pr_auc": average_precision_score(y_test, proba),
            "roc_auc": roc_auc_score(y_test, proba),
            "precision": precision_score(y_test, predicted, zero_division=0),
            "recall": recall_score(y_test, predicted),
        }

        mlflow.log_params(params)
        mlflow.log_param("threshold", THRESHOLD)
        mlflow.log_param("train_rows", len(train))
        mlflow.log_param("test_rows", len(test))
        mlflow.log_param("test_fraud_rows", int(y_test.sum()))
        mlflow.log_metrics(metrics)

        importance = pd.Series(model.feature_importances_, index=FEATURE_COLUMNS).sort_values(
            ascending=False
        )
        mlflow.log_dict(importance.round(4).to_dict(), "feature_importance.json")

        mlflow.xgboost.log_model(model, name="model", input_example=x_test.head(5))

        MODEL_DIR.mkdir(exist_ok=True)
        model.save_model(MODEL_DIR / "fraud_xgb.json")

        print(f"train rows: {len(train)}  test rows: {len(test)}  test fraud: {int(y_test.sum())}")
        print(f"scale_pos_weight: {params['scale_pos_weight']:.2f}")
        for name, value in metrics.items():
            print(f"{name}: {value:.4f}")
        print("\ntop features:")
        print(importance.head(8).round(4).to_string())


if __name__ == "__main__":
    main()
