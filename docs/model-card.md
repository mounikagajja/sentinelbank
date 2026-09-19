# Model card: SentinelBank fraud classifier

## What it does

The model looks at one bank transaction and gives it a score between 0 and 1. A higher score means the transaction is more likely to be fraud. It uses the transaction itself plus the recent history of the account.

## Data

The data is fake, made by a script in this repo. Real bank data is not public. The public fraud datasets that do exist hide the details: no merchant names, no customer IDs, no real timestamps. This project needs those details because the AI assistant has to explain a flag to a customer in plain words, like "a $900 charge at Newegg at 3am."

The script gives every customer their own habits: two or three favorite shopping categories, their own spending level (some people spend three times more than others), and traits like being a night owl, taking trips abroad, or doing several purchases in one shopping trip. It then adds five kinds of fraud, each one labeled:

- Card testing: many tiny online charges in a short time, to check if a stolen card works
- Impossible travel: a purchase at home, then another one far away too soon to have traveled there
- Night high value: large purchases in the early hours of the morning
- ATM drain: several big cash withdrawals in a few minutes
- Subtle takeover: one or two normal-looking purchases that are just bigger than usual

The current run makes 32,624 transactions across 282 accounts, with 638 marked as fraud (1.96%).

The first version of this script was too easy. Fraud looked nothing like normal spending, and the first model caught 100% of it. That was not a good model, it was bad data. So the script was rewritten so normal behavior overlaps with fraud: shopping trips look like card testing, travelers look like impossible travel, night owls look like night fraud, and a one-off laptop purchase looks like a big fraudulent one.

## Features

The model uses 20 numbers per transaction. Every one of them is built only from the current transaction and earlier ones on the same account. Nothing looks into the future, because at the moment a real payment is scored, the future has not happened yet.

- About the transaction: amount, hour of day, day of week, is it night, is it a weekend, channel (card, online, ATM), merchant category, type
- About location: is the country different from the customer's home country, did the country change since the last transaction
- About speed: how many transactions and how much money in the last hour and the last 24 hours, how many seconds since the last transaction, and how busy today is compared to this account's normal day
- About the customer's own habits: this amount compared to what they usually spend, this amount compared to what they usually spend in this category, how often they shop in this category, and whether this hour of day is new for them

## How it was trained

The model is XGBoost, which builds 400 small decision trees where each tree fixes the mistakes of the ones before it. Because only 2% of transactions are fraud, a lazy model could say "never fraud" and be right 98% of the time. To stop that, each fraud example is given about 51 times more weight during training.

The data is split by date, not randomly: the first 45 days are for training (23,958 rows) and the last 15 days are for testing (8,666 rows with 176 fraud). A random split would let the model learn from transactions that happen after the ones it is tested on, which is cheating.

Every training run is recorded in MLflow so the runs can be compared later.

As a starting point for comparison, an Isolation Forest (which never sees the fraud labels at all) was tried first and scored 0.46 PR-AUC.

## Results

The main score is PR-AUC, which came out at 0.8259. PR-AUC is used instead of accuracy because with 2% fraud, a model that flags nothing still gets 98% accuracy, so accuracy means nothing here.

The score has to be turned into a yes or no by picking a cutoff. At a cutoff of 0.7 the model catches 132 of the 176 fraud transactions (75%) and wrongly flags 38 out of 8,490 normal ones, so about 78% of what it flags really is fraud.

There is no single correct cutoff. A lower one catches more fraud but annoys more real customers. The full table of cutoffs is in `docs/evaluation.md`, and the right one depends on which mistake costs the bank more.

## What it does not do well

The model is much better at some kinds of fraud than others. At a cutoff of 0.7 it catches 92% of card testing, 89% of night high value, 83% of ATM drains, 79% of impossible travel, but only 33% of subtle takeovers.

A subtle takeover is a purchase at a normal time of day, in the customer's own city, in a category they sometimes use, for two to four times their usual amount. Nothing about it is extreme, so the model has almost nothing to go on. Two rounds of new features raised it from 15% to 33%.

Catching more would need information this data does not have: what device was used, what IP address it came from, whether the customer had ever logged in from that device before, and how risky the merchant is. Those could be faked in the generator, but that would mean inventing the exact clue that makes the fraud catchable, which proves nothing. So it stays here as a known weakness.

## How to reproduce these numbers

```bash
docker compose up -d
uv sync --all-groups
uv run alembic upgrade head
uv run python -m data.generator.generate --reset
uv run python -m ml.features.build
uv run python -m ml.training.baseline
uv run python -m ml.training.train
uv run python -m ml.evaluation.report
```

Every number on this page comes from running those commands with the default seed.