# Fraud model evaluation

Model: `models\fraud_xgb.json`. Test set: last 15 days, 8666 rows, 176 fraud.

PR-AUC: 0.7843
ROC-AUC: 0.9777

## Threshold sweep

|   threshold |   flagged |   precision |   recall |     f1 |
|------------:|----------:|------------:|---------:|-------:|
|         0.1 |       510 |      0.298  |   0.8636 | 0.4431 |
|         0.2 |       369 |      0.393  |   0.8239 | 0.5321 |
|         0.3 |       305 |      0.4525 |   0.7841 | 0.5738 |
|         0.4 |       260 |      0.5231 |   0.7727 | 0.6239 |
|         0.5 |       213 |      0.6103 |   0.7386 | 0.6684 |
|         0.6 |       187 |      0.6791 |   0.7216 | 0.6997 |
|         0.7 |       162 |      0.7654 |   0.7045 | 0.7337 |
|         0.8 |       142 |      0.838  |   0.6761 | 0.7484 |
|         0.9 |       116 |      0.8966 |   0.5909 | 0.7123 |

Best F1 at threshold 0.8.

## Confusion matrix at 0.8

| | Predicted normal | Predicted fraud |
|---|---|---|
| Actual normal | 8467 | 23 |
| Actual fraud | 57 | 119 |

## Recall by fraud pattern at 0.8

| pattern           |   fraud_rows |   caught |   recall |
|:------------------|-------------:|---------:|---------:|
| atm_drain         |           30 |       23 |   0.7667 |
| card_testing      |           52 |       48 |   0.9231 |
| impossible_travel |           28 |       20 |   0.7143 |
| night_high_value  |           27 |       22 |   0.8148 |
| subtle_takeover   |           39 |        6 |   0.1538 |
