import argparse
import random
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from faker import Faker
from sqlalchemy import delete

from backend.app.db.session import SessionLocal
from backend.app.models import Account, Customer, FraudFlag, Transaction

MERCHANTS = {
    "grocery": ["Fry's Food", "Safeway", "Whole Foods", "Trader Joe's"],
    "restaurant": ["Chipotle", "Olive Garden", "Pita Jungle", "Starbucks"],
    "fuel": ["Shell", "Chevron", "QuikTrip", "Circle K"],
    "retail": ["Target", "Walmart", "Best Buy", "Costco"],
    "online": ["Amazon", "eBay", "Etsy", "Steam"],
    "travel": ["Delta Air Lines", "Marriott", "Uber", "Hertz"],
    "utilities": ["APS Electric", "Cox Communications", "City of Tempe Water"],
    "electronics": ["Apple Store", "Newegg", "Micro Center"],
}

AMOUNT_RANGES = {
    "grocery": (15, 180),
    "restaurant": (8, 90),
    "fuel": (20, 80),
    "retail": (10, 300),
    "online": (5, 250),
    "travel": (80, 900),
    "utilities": (40, 220),
    "electronics": (50, 1500),
}

HOME_CITIES = [
    ("Tempe", "US"),
    ("Phoenix", "US"),
    ("Scottsdale", "US"),
    ("Mesa", "US"),
    ("Chandler", "US"),
]
FAR_CITIES = [
    ("London", "GB"),
    ("Tokyo", "JP"),
    ("Sydney", "AU"),
    ("Berlin", "DE"),
    ("Toronto", "CA"),
    ("Dubai", "AE"),
]

HOUR_WEIGHTS = [1, 1, 1, 1, 1, 2, 4, 6, 8, 9, 9, 10, 10, 9, 9, 9, 9, 10, 10, 9, 7, 5, 3, 2]


def money(value: float) -> Decimal:
    return Decimal(str(round(value, 2)))


def daytime(day_start: datetime, rng: random.Random) -> datetime:
    hour = rng.choices(range(24), weights=HOUR_WEIGHTS)[0]
    return day_start + timedelta(hours=hour, minutes=rng.randint(0, 59), seconds=rng.randint(0, 59))


def normal_transaction(
    account: Account, when: datetime, home: tuple[str, str], rng: random.Random
) -> Transaction:
    category = rng.choice(list(MERCHANTS))
    lo, hi = AMOUNT_RANGES[category]
    if category == "online":
        channel = "online"
    else:
        channel = rng.choices(["pos", "atm", "online"], weights=[7, 1, 2])[0]
    if channel == "atm":
        return Transaction(
            account_id=account.id,
            amount=money(rng.choice([20, 40, 60, 100, 200])),
            transaction_type="withdrawal",
            channel="atm",
            merchant_name="ATM Withdrawal",
            merchant_category="cash",
            city=home[0],
            country=home[1],
            occurred_at=when,
            is_fraud=False,
        )
    return Transaction(
        account_id=account.id,
        amount=money(rng.uniform(lo, hi)),
        transaction_type="purchase",
        channel=channel,
        merchant_name=rng.choice(MERCHANTS[category]),
        merchant_category=category,
        city=home[0],
        country=home[1],
        occurred_at=when,
        is_fraud=False,
    )


def card_testing(
    account: Account, day_start: datetime, home: tuple[str, str], rng: random.Random
) -> list[Transaction]:
    start = daytime(day_start, rng)
    return [
        Transaction(
            account_id=account.id,
            amount=money(rng.uniform(0.5, 3.0)),
            transaction_type="purchase",
            channel="online",
            merchant_name=rng.choice(MERCHANTS["online"]),
            merchant_category="online",
            city=home[0],
            country=home[1],
            occurred_at=start + timedelta(seconds=i * rng.randint(20, 90)),
            is_fraud=True,
        )
        for i in range(rng.randint(5, 8))
    ]


def impossible_travel(
    account: Account, day_start: datetime, home: tuple[str, str], rng: random.Random
) -> list[Transaction]:
    first = daytime(day_start, rng)
    far = rng.choice(FAR_CITIES)
    category = rng.choice(["retail", "travel", "electronics"])
    return [
        normal_transaction(account, first, home, rng),
        Transaction(
            account_id=account.id,
            amount=money(rng.uniform(100, 800)),
            transaction_type="purchase",
            channel="pos",
            merchant_name=rng.choice(MERCHANTS[category]),
            merchant_category=category,
            city=far[0],
            country=far[1],
            occurred_at=first + timedelta(minutes=rng.randint(30, 90)),
            is_fraud=True,
        ),
    ]


def night_high_value(
    account: Account, day_start: datetime, home: tuple[str, str], rng: random.Random
) -> list[Transaction]:
    when = day_start + timedelta(hours=rng.randint(1, 4), minutes=rng.randint(0, 59))
    category = rng.choice(["electronics", "retail"])
    return [
        Transaction(
            account_id=account.id,
            amount=money(rng.uniform(800, 2500)),
            transaction_type="purchase",
            channel="online",
            merchant_name=rng.choice(MERCHANTS[category]),
            merchant_category=category,
            city=home[0],
            country=home[1],
            occurred_at=when + timedelta(minutes=i * rng.randint(3, 15)),
            is_fraud=True,
        )
        for i in range(rng.randint(1, 2))
    ]


def atm_drain(
    account: Account, day_start: datetime, home: tuple[str, str], rng: random.Random
) -> list[Transaction]:
    start = daytime(day_start, rng)
    return [
        Transaction(
            account_id=account.id,
            amount=money(rng.choice([200, 300, 400, 500])),
            transaction_type="withdrawal",
            channel="atm",
            merchant_name="ATM Withdrawal",
            merchant_category="cash",
            city=home[0],
            country=home[1],
            occurred_at=start + timedelta(minutes=i * rng.randint(2, 6)),
            is_fraud=True,
        )
        for i in range(rng.randint(3, 5))
    ]


PATTERNS = [card_testing, impossible_travel, night_high_value, atm_drain]


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed SentinelBank with synthetic data")
    parser.add_argument("--customers", type=int, default=200)
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument("--fraud-rate", type=float, default=0.02)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--reset", action="store_true", help="delete existing rows first")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    Faker.seed(args.seed)
    fake = Faker()

    end = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=args.days)

    with SessionLocal() as db:
        if args.reset:
            for table in (FraudFlag, Transaction, Account, Customer):
                db.execute(delete(table))

        customers = []
        for _ in range(args.customers):
            city, country = rng.choice(HOME_CITIES)
            customers.append(
                Customer(
                    full_name=fake.name(),
                    email=fake.unique.email(),
                    home_city=city,
                    home_country=country,
                )
            )
        db.add_all(customers)
        db.flush()

        accounts = []
        for c in customers:
            kinds = ["checking"] + (["savings"] if rng.random() < 0.4 else [])
            for kind in kinds:
                accounts.append(
                    Account(
                        customer_id=c.id,
                        account_type=kind,
                        balance=money(rng.uniform(500, 25000)),
                    )
                )
        db.add_all(accounts)
        db.flush()

        home_of = {c.id: (c.home_city, c.home_country) for c in customers}

        normal = []
        for acc in accounts:
            home = home_of[acc.customer_id]
            per_day = rng.uniform(0.5, 3.0)
            for d in range(args.days):
                day_start = start + timedelta(days=d)
                count = max(0, round(rng.gauss(per_day, 1.0)))
                for _ in range(count):
                    normal.append(normal_transaction(acc, daytime(day_start, rng), home, rng))

        target = int(len(normal) * args.fraud_rate)
        fraud = []
        fraud_count = 0
        while fraud_count < target:
            acc = rng.choice(accounts)
            day_start = start + timedelta(days=rng.randint(0, args.days - 1))
            pattern = rng.choice(PATTERNS)
            fraud.extend(pattern(acc, day_start, home_of[acc.customer_id], rng))
            fraud_count = sum(1 for t in fraud if t.is_fraud)

        db.add_all(normal + fraud)
        db.commit()

        total = len(normal) + len(fraud)
        print(f"customers: {len(customers)}")
        print(f"accounts: {len(accounts)}")
        print(f"transactions: {total}")
        print(f"fraud labeled: {fraud_count} ({fraud_count / total:.2%})")


if __name__ == "__main__":
    main()
