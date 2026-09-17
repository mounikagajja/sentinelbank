# Fraud model evaluation

Model: `models\fraud_xgb.json`. Test set: last 15 days, 8666 rows, 176 fraud.

PR-AUC: 0.7724
ROC-AUC: 0.9769

## Threshold sweep

|   threshold |   flagged |   precision |   recall |     f1 |
|------------:|----------:|------------:|---------:|-------:|
|         0.1 |       613 |      0.248  |   0.8636 | 0.3853 |
|         0.2 |       407 |      0.3587 |   0.8295 | 0.5009 |
|         0.3 |       312 |      0.4423 |   0.7841 | 0.5656 |
|         0.4 |       273 |      0.4945 |   0.767  | 0.6013 |
|         0.5 |       230 |      0.5652 |   0.7386 | 0.6404 |
|         0.6 |       201 |      0.6269 |   0.7159 | 0.6684 |
|         0.7 |       167 |      0.7305 |   0.6932 | 0.7114 |
|         0.8 |       143 |      0.8252 |   0.6705 | 0.7398 |
|         0.9 |       121 |      0.8926 |   0.6136 | 0.7273 |

Best F1 at threshold 0.8.

## Confusion matrix at 0.8

| | Predicted normal | Predicted fraud |
|---|---|---|
| Actual normal | 8465 | 25 |
| Actual fraud | 58 | 118 |

## Recall by fraud pattern at 0.8

| pattern           |   fraud_rows |   caught |   recall |
|:------------------|-------------:|---------:|---------:|
| atm_drain         |           30 |       23 |   0.7667 |
| card_testing      |           52 |       45 |   0.8654 |
| impossible_travel |           28 |       20 |   0.7143 |
| night_high_value  |           27 |       24 |   0.8889 |
| subtle_takeover   |           39 |        6 |   0.1538 |
