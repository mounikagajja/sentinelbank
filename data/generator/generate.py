import argparse
import random
from collections import Counter
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
FAR_US_CITIES = [
    ("New York", "US"),
    ("Chicago", "US"),
    ("Miami", "US"),
    ("Seattle", "US"),
    ("Boston", "US"),
]

DAY_WEIGHTS = [1, 1, 1, 1, 1, 2, 4, 6, 8, 9, 9, 10, 10, 9, 9, 9, 9, 10, 10, 9, 7, 5, 3, 2]
NIGHT_OWL_WEIGHTS = [6, 7, 7, 6, 5, 3, 2, 2, 3, 4, 4, 5, 5, 5, 5, 5, 6, 7, 8, 9, 9, 8, 7, 6]

Location = tuple[str, str]


def money(value: float) -> Decimal:
    return Decimal(str(round(value, 2)))


def make_profile(home: Location, rng: random.Random) -> dict:
    return {
        "home": home,
        "favorites": rng.sample(list(MERCHANTS), k=rng.randint(2, 3)),
        "scale": round(rng.lognormvariate(0.0, 0.5), 2),
        "per_day": rng.uniform(0.5, 3.0),
        "night_owl": rng.random() < 0.10,
        "bursty": rng.random() < 0.25,
        "trip": None,
    }


def plan_trip(profile: dict, days: int, rng: random.Random) -> dict:
    if rng.random() < 0.10 and days >= 8:
        length = rng.randint(3, 6)
        profile["trip"] = {
            "start": rng.randint(0, days - length - 1),
            "length": length,
            "city": rng.choice(FAR_CITIES),
        }
    return profile


def typical_amount(profile: dict) -> float:
    return 120.0 * profile["scale"]


def when_at(day_start: datetime, profile: dict, rng: random.Random) -> datetime:
    weights = NIGHT_OWL_WEIGHTS if profile["night_owl"] else DAY_WEIGHTS
    hour = rng.choices(range(24), weights=weights)[0]
    return day_start + timedelta(hours=hour, minutes=rng.randint(0, 59), seconds=rng.randint(0, 59))


def location_on(day_index: int, profile: dict) -> Location:
    trip = profile["trip"]
    if trip and trip["start"] <= day_index < trip["start"] + trip["length"]:
        return trip["city"]
    return profile["home"]


def purchase(
    account: Account,
    when: datetime,
    location: Location,
    category: str,
    amount: float,
    channel: str,
    rng: random.Random,
    is_fraud: bool = False,
    pattern: str | None = None,
) -> Transaction:
    if category == "cash":
        merchant, transaction_type = "ATM Withdrawal", "withdrawal"
    else:
        merchant, transaction_type = rng.choice(MERCHANTS[category]), "purchase"
    return Transaction(
        account_id=account.id,
        amount=money(amount),
        transaction_type=transaction_type,
        channel=channel,
        merchant_name=merchant,
        merchant_category=category,
        city=location[0],
        country=location[1],
        occurred_at=when,
        is_fraud=is_fraud,
        pattern=pattern,
    )


def normal_transaction(
    account: Account,
    when: datetime,
    profile: dict,
    rng: random.Random,
    location: Location | None = None,
) -> Transaction:
    location = location or profile["home"]
    if rng.random() < 0.02:
        return purchase(
            account, when, location, "electronics", rng.uniform(800, 2500), "online", rng
        )
    category = (
        rng.choice(profile["favorites"]) if rng.random() < 0.7 else rng.choice(list(MERCHANTS))
    )
    channel = (
        "online"
        if category == "online"
        else rng.choices(["pos", "atm", "online"], weights=[7, 1, 2])[0]
    )
    if channel == "atm":
        return purchase(
            account, when, location, "cash", rng.choice([20, 40, 60, 100, 200]), "atm", rng
        )
    lo, hi = AMOUNT_RANGES[category]
    return purchase(
        account, when, location, category, rng.uniform(lo, hi) * profile["scale"], channel, rng
    )


def shopping_burst(
    account: Account, day_start: datetime, profile: dict, rng: random.Random, location: Location
) -> list[Transaction]:
    start = when_at(day_start, profile, rng)
    rows = []
    for i in range(rng.randint(3, 5)):
        category = rng.choice(["retail", "grocery", "restaurant"])
        lo, hi = AMOUNT_RANGES[category]
        when = start + timedelta(minutes=i * rng.randint(5, 15))
        rows.append(
            purchase(
                account,
                when,
                location,
                category,
                rng.uniform(lo, hi) * profile["scale"],
                "pos",
                rng,
            )
        )
    return rows


def card_testing(
    account: Account, day_start: datetime, profile: dict, rng: random.Random
) -> list[Transaction]:
    start = when_at(day_start, profile, rng)
    fast = rng.random() < 0.6
    count = rng.randint(5, 8) if fast else rng.randint(3, 4)
    spacing = (20, 90) if fast else (300, 1200)
    amounts = (0.5, 3.0) if fast else (1.0, 15.0)
    return [
        purchase(
            account,
            start + timedelta(seconds=i * rng.randint(*spacing)),
            profile["home"],
            "online",
            rng.uniform(*amounts),
            "online",
            rng,
            True,
            "card_testing",
        )
        for i in range(count)
    ]


def impossible_travel(
    account: Account, day_start: datetime, profile: dict, rng: random.Random
) -> list[Transaction]:
    first = when_at(day_start, profile, rng)
    far = rng.choice(FAR_CITIES if rng.random() < 0.6 else FAR_US_CITIES)
    category = rng.choice(["retail", "travel", "electronics"])
    return [
        normal_transaction(account, first, profile, rng),
        purchase(
            account,
            first + timedelta(minutes=rng.randint(30, 120)),
            far,
            category,
            rng.uniform(100, 800),
            "pos",
            rng,
            True,
            "impossible_travel",
        ),
    ]


def night_high_value(
    account: Account, day_start: datetime, profile: dict, rng: random.Random
) -> list[Transaction]:
    when = day_start + timedelta(hours=rng.randint(1, 4), minutes=rng.randint(0, 59))
    category = rng.choice(["electronics", "retail"])
    return [
        purchase(
            account,
            when + timedelta(minutes=i * rng.randint(3, 15)),
            profile["home"],
            category,
            rng.uniform(800, 2500),
            "online",
            rng,
            True,
            "night_high_value",
        )
        for i in range(rng.randint(1, 2))
    ]


def atm_drain(
    account: Account, day_start: datetime, profile: dict, rng: random.Random
) -> list[Transaction]:
    start = when_at(day_start, profile, rng)
    return [
        purchase(
            account,
            start + timedelta(minutes=i * rng.randint(2, 6)),
            profile["home"],
            "cash",
            rng.choice([200, 300, 400, 500]),
            "atm",
            rng,
            True,
            "atm_drain",
        )
        for i in range(rng.randint(3, 5))
    ]


def subtle_takeover(
    account: Account, day_start: datetime, profile: dict, rng: random.Random
) -> list[Transaction]:
    hour = rng.choices(range(24), weights=DAY_WEIGHTS)[0]
    start = day_start + timedelta(hours=hour, minutes=rng.randint(0, 59))
    unusual = [c for c in MERCHANTS if c not in profile["favorites"]]
    category = rng.choice(unusual)
    return [
        purchase(
            account,
            start + timedelta(minutes=i * rng.randint(20, 90)),
            profile["home"],
            category,
            typical_amount(profile) * rng.uniform(2, 4),
            rng.choice(["online", "pos"]),
            rng,
            True,
            "subtle_takeover",
        )
        for i in range(rng.randint(1, 2))
    ]


PATTERNS = [card_testing, impossible_travel, night_high_value, atm_drain, subtle_takeover]
PATTERN_WEIGHTS = [1, 4, 3, 1, 3]


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

        profiles = {
            c.id: plan_trip(make_profile((c.home_city, c.home_country), rng), args.days, rng)
            for c in customers
        }

        accounts = []
        for c in customers:
            kinds = ["checking"] + (["savings"] if rng.random() < 0.4 else [])
            for kind in kinds:
                accounts.append(
                    Account(
                        customer_id=c.id, account_type=kind, balance=money(rng.uniform(500, 25000))
                    )
                )
        db.add_all(accounts)
        db.flush()

        normal = []
        for acc in accounts:
            profile = profiles[acc.customer_id]
            for d in range(args.days):
                day_start = start + timedelta(days=d)
                location = location_on(d, profile)
                count = max(0, round(rng.gauss(profile["per_day"], 1.0)))
                for _ in range(count):
                    normal.append(
                        normal_transaction(
                            acc, when_at(day_start, profile, rng), profile, rng, location
                        )
                    )
                if profile["bursty"] and rng.random() < 0.08:
                    normal.extend(shopping_burst(acc, day_start, profile, rng, location))

        target = int(len(normal) * args.fraud_rate)
        fraud = []
        fraud_count = 0
        while fraud_count < target:
            acc = rng.choice(accounts)
            day_start = start + timedelta(days=rng.randint(0, args.days - 1))
            pattern = rng.choices(PATTERNS, weights=PATTERN_WEIGHTS)[0]
            fraud.extend(pattern(acc, day_start, profiles[acc.customer_id], rng))
            fraud_count = sum(1 for t in fraud if t.is_fraud)

        db.add_all(normal + fraud)
        db.commit()

        total = len(normal) + len(fraud)
        by_pattern = Counter(t.pattern for t in fraud if t.is_fraud)
        print(f"customers: {len(customers)}")
        print(f"accounts: {len(accounts)}")
        print(f"transactions: {total}")
        print(f"fraud labeled: {fraud_count} ({fraud_count / total:.2%})")
        for name, n in sorted(by_pattern.items()):
            print(f"  {name}: {n}")


if __name__ == "__main__":
    main()
