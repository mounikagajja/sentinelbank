# Fraud model evaluation

Model: `models\fraud_xgb.json`.
Test set: last 15 days, 8666 rows, 176 fraud.

PR-AUC: 0.8259
ROC-AUC: 0.9882

## Threshold sweep

|   threshold |   flagged |   precision |   recall |     f1 |
|------------:|----------:|------------:|---------:|-------:|
|         0.1 |       401 |      0.394  |   0.8977 | 0.5477 |
|         0.2 |       303 |      0.4917 |   0.8466 | 0.6221 |
|         0.3 |       256 |      0.5703 |   0.8295 | 0.6759 |
|         0.4 |       225 |      0.6178 |   0.7898 | 0.6933 |
|         0.5 |       205 |      0.6634 |   0.7727 | 0.7139 |
|         0.6 |       184 |      0.7337 |   0.767  | 0.75   |
|         0.7 |       170 |      0.7765 |   0.75   | 0.763  |
|         0.8 |       150 |      0.8067 |   0.6875 | 0.7423 |
|         0.9 |       122 |      0.877  |   0.608  | 0.7181 |

Best F1 at threshold 0.7.

## Confusion matrix at 0.7

| | Predicted normal | Predicted fraud |
|---|---|---|
| Actual normal | 8452 | 38 |
| Actual fraud | 44 | 132 |

## Recall by fraud pattern at 0.7

| pattern           |   fraud_rows |   caught |   recall |
|:------------------|-------------:|---------:|---------:|
| atm_drain         |           30 |       25 |   0.8333 |
| card_testing      |           52 |       48 |   0.9231 |
| impossible_travel |           28 |       22 |   0.7857 |
| night_high_value  |           27 |       24 |   0.8889 |
| subtle_takeover   |           39 |       13 |   0.3333 |
