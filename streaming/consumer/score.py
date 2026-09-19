import argparse
import json
import signal
import sys
from datetime import datetime

import numpy as np
from confluent_kafka import Consumer, KafkaError
from sqlalchemy import select, text
from xgboost import XGBClassifier

from backend.app.core.config import get_settings
from backend.app.db.session import SessionLocal
from backend.app.models import FraudFlag
from ml.features.build import FEATURE_COLUMNS
from ml.features.online import compute_features

settings = get_settings()
MODEL_VERSION = "xgb-v1"

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


def main() -> None:
    parser = argparse.ArgumentParser(description="Score transactions from Redpanda")
    parser.add_argument("--from-beginning", action="store_true")
    parser.add_argument("--max-messages", type=int, default=0, help="0 means run forever")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

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

    processed = 0
    flagged = 0

    try:
        while running:
            message = consumer.poll(1.0)
            if message is None:
                continue
            if message.error():
                if message.error().code() == KafkaError._PARTITION_EOF:
                    continue
                print(f"consumer error: {message.error()}", file=sys.stderr)
                continue

            payload = json.loads(message.value().decode("utf-8"))

            with SessionLocal() as db:
                probability, is_flagged = score_message(db, model, payload)
                if is_flagged:
                    existing = db.scalar(
                        select(FraudFlag).where(
                            FraudFlag.transaction_id == payload["transaction_id"]
                        )
                    )
                    if existing is None:
                        db.add(
                            FraudFlag(
                                transaction_id=payload["transaction_id"],
                                fraud_score=probability,
                                model_version=MODEL_VERSION,
                            )
                        )
                        flagged += 1
                    db.commit()

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
        consumer.close()
        print(f"processed: {processed}  flagged: {flagged}")


if __name__ == "__main__":
    main()
