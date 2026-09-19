import argparse
import json
import time
from datetime import datetime

from confluent_kafka import Producer
from sqlalchemy import select

from backend.app.core.config import get_settings
from backend.app.db.session import SessionLocal
from backend.app.models import Transaction

settings = get_settings()


def to_message(txn: Transaction) -> dict:
    return {
        "transaction_id": txn.id,
        "account_id": txn.account_id,
        "amount": float(txn.amount),
        "transaction_type": txn.transaction_type,
        "channel": txn.channel,
        "merchant_name": txn.merchant_name,
        "merchant_category": txn.merchant_category,
        "city": txn.city,
        "country": txn.country,
        "occurred_at": txn.occurred_at.isoformat(),
    }


def report(err, msg) -> None:
    if err is not None:
        print(f"delivery failed: {err}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish transactions to Redpanda")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--rate", type=float, default=5.0, help="messages per second")
    parser.add_argument("--since", type=str, default=None, help="ISO date, only newer transactions")
    args = parser.parse_args()

    producer = Producer({"bootstrap.servers": settings.redpanda_broker, "linger.ms": 50})

    query = select(Transaction).order_by(Transaction.occurred_at, Transaction.id)
    if args.since:
        query = query.where(Transaction.occurred_at >= datetime.fromisoformat(args.since))
    query = query.limit(args.limit)

    delay = 1.0 / args.rate if args.rate > 0 else 0.0
    sent = 0

    with SessionLocal() as db:
        for txn in db.scalars(query):
            producer.produce(
                topic=settings.transactions_topic,
                key=str(txn.account_id),
                value=json.dumps(to_message(txn)).encode("utf-8"),
                callback=report,
            )
            producer.poll(0)
            sent += 1
            if delay:
                time.sleep(delay)

    producer.flush(10)
    print(f"published {sent} messages to {settings.transactions_topic}")


if __name__ == "__main__":
    main()
