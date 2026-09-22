import argparse
import json
import signal
import sys
import time
from datetime import datetime

import numpy as np
from confluent_kafka import Consumer, KafkaError, Producer
from prometheus_client import Counter, Histogram, start_http_server
from sqlalchemy import select, text
from xgboost import XGBClassifier

from backend.app.core.config import get_settings
from backend.app.db.session import SessionLocal
from backend.app.models import FraudFlag
from ml.features.build import FEATURE_COLUMNS
from ml.features.online import compute_features

settings = get_settings()
MODEL_VERSION = "xgb-v1"
METRICS_PORT = 9100

SCORED = Counter("sentinelbank_transactions_scored_total", "Transactions scored")
FLAGGED = Counter("sentinelbank_flags_raised_total", "Fraud flags written to the database")
ERRORS = Counter("sentinelbank_scoring_errors_total", "Messages that failed to score")
LATENCY = Histogram(
    "sentinelbank_scoring_seconds",
    "Time to compute features, score, and write one transaction",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)
SCORES = Histogram(
    "sentinelbank_fraud_score",
    "Distribution of fraud scores produced by the model",
    buckets=(0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0),
)

HOME_COUNTRY_SQL = text("""
    SELECT c.home_country
    FROM accounts a JOIN customers c ON c.id = a.customer_id
    WHERE a.id = :account_id
""")

running = True


def stop(signum, frame) -> None:
    global running
    running = False
    print("\nshutting down")


def load_model() -> XGBClassifier:
    model = XGBClassifier()
    model.load_model(settings.model_path)
    return model


def score_message(db, model: XGBClassifier, payload: dict) -> tuple[float, bool]:
    home_country = db.execute(HOME_COUNTRY_SQL, {"account_id": payload["account_id"]}).scalar_one()

    features = compute_features(
        db,
        transaction_id=payload["transaction_id"],
        account_id=payload["account_id"],
        amount=payload["amount"],
        transaction_type=payload["transaction_type"],
        channel=payload["channel"],
        merchant_category=payload["merchant_category"],
        country=payload["country"],
        home_country=home_country,
        occurred_at=datetime.fromisoformat(payload["occurred_at"]),
    )

    vector = np.array([[features[name] for name in FEATURE_COLUMNS]], dtype=float)
    probability = float(model.predict_proba(vector)[0, 1])
    return probability, probability >= settings.fraud_threshold


def write_flag(db, transaction_id: int, probability: float) -> bool:
    """Insert a fraud flag if one does not already exist. Returns True if inserted."""
    existing = db.scalar(select(FraudFlag).where(FraudFlag.transaction_id == transaction_id))
    if existing is not None:
        return False
    db.add(
        FraudFlag(
            transaction_id=transaction_id,
            fraud_score=probability,
            model_version=MODEL_VERSION,
        )
    )
    db.flush()
    return True


def score_event(payload: dict, probability: float, is_flagged: bool) -> bytes:
    event = {
        "transaction_id": payload["transaction_id"],
        "account_id": payload["account_id"],
        "amount": payload["amount"],
        "merchant_name": payload["merchant_name"],
        "merchant_category": payload["merchant_category"],
        "channel": payload["channel"],
        "city": payload["city"],
        "country": payload["country"],
        "occurred_at": payload["occurred_at"],
        "score": round(probability, 4),
        "flagged": is_flagged,
        "model_version": MODEL_VERSION,
    }
    return json.dumps(event).encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Score transactions from Redpanda")
    parser.add_argument("--from-beginning", action="store_true")
    parser.add_argument("--max-messages", type=int, default=0, help="0 means run forever")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    start_http_server(METRICS_PORT)
    model = load_model()
    consumer = Consumer(
        {
            "bootstrap.servers": settings.redpanda_broker,
            "group.id": settings.consumer_group,
            "auto.offset.reset": "earliest" if args.from_beginning else "latest",
            "enable.auto.commit": False,
        }
    )
    consumer.subscribe([settings.transactions_topic])
    producer = Producer({"bootstrap.servers": settings.redpanda_broker, "linger.ms": 20})

    processed = 0
    flagged = 0

    try:
        while running:
            message = consumer.poll(1.0)
            producer.poll(0)
            if message is None:
                continue
            if message.error():
                if message.error().code() == KafkaError._PARTITION_EOF:
                    continue
                print(f"consumer error: {message.error()}", file=sys.stderr)
                continue

            payload = json.loads(message.value().decode("utf-8"))
            started = time.perf_counter()

            try:
                with SessionLocal() as db:
                    probability, is_flagged = score_message(db, model, payload)
                    if is_flagged and write_flag(db, payload["transaction_id"], probability):
                        flagged += 1
                        FLAGGED.inc()
                    db.commit()
            except Exception as exc:
                ERRORS.inc()
                print(f"failed to score {payload.get('transaction_id')}: {exc}", file=sys.stderr)
                consumer.commit(message)
                continue

            LATENCY.observe(time.perf_counter() - started)
            SCORES.observe(probability)
            SCORED.inc()

            producer.produce(
                topic=settings.scores_topic,
                key=str(payload["account_id"]),
                value=score_event(payload, probability, is_flagged),
            )
            consumer.commit(message)
            processed += 1

            if is_flagged:
                print(
                    f"FLAG txn={payload['transaction_id']} account={payload['account_id']} "
                    f"amount={payload['amount']:.2f} {payload['merchant_name']} "
                    f"score={probability:.4f}"
                )

            if args.max_messages and processed >= args.max_messages:
                break
    finally:
        producer.flush(5)
        consumer.close()
        print(f"processed: {processed}  flagged: {flagged}")


if __name__ == "__main__":
    main()
