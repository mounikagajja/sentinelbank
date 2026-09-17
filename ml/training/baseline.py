import mlflow
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import average_precision_score, precision_score, recall_score, roc_auc_score

from ml.features.build import FEATURE_COLUMNS, TARGET
from ml.training.split import time_split

TRACKING_URI = "sqlite:///mlflow.db"
EXPERIMENT = "sentinelbank-fraud"


def main() -> None:
    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT)

    df = pd.read_parquet("data/processed/features.parquet")
    train, test = time_split(df)
    x_train = train[FEATURE_COLUMNS]
    x_test, y_test = test[FEATURE_COLUMNS], test[TARGET]

    params = {"n_estimators": 300, "contamination": 0.02, "random_state": 42}

    with mlflow.start_run(run_name="isolation_forest_baseline"):
        model = IsolationForest(**params).fit(x_train)

        anomaly_score = -model.score_samples(x_test)
        predicted = (model.predict(x_test) == -1).astype(int)

        metrics = {
            "pr_auc": average_precision_score(y_test, anomaly_score),
            "roc_auc": roc_auc_score(y_test, anomaly_score),
            "precision": precision_score(y_test, predicted, zero_division=0),
            "recall": recall_score(y_test, predicted),
        }

        mlflow.log_params(params)
        mlflow.log_param("train_rows", len(train))
        mlflow.log_param("test_rows", len(test))
        mlflow.log_param("test_fraud_rows", int(y_test.sum()))
        mlflow.log_metrics(metrics)

        print(f"train rows: {len(train)}  test rows: {len(test)}  test fraud: {int(y_test.sum())}")
        for name, value in metrics.items():
            print(f"{name}: {value:.4f}")


if __name__ == "__main__":
    main()