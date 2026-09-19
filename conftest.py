from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.security import User, get_current_user, require_analyst
from backend.app.db.session import engine, get_db
from backend.app.main import app
from backend.app.models import Account, Customer, FraudFlag, Transaction

BASE = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
def db() -> Generator[Session, None, None]:
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db):
    analyst = User(username="analyst", role="analyst")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: analyst
    app.dependency_overrides[require_analyst] = lambda: analyst
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def viewer_client(db):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: User(username="viewer", role="viewer")
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def seeded(db):
    customer = Customer(
        full_name="Api Test", email="api@example.com", home_city="Tempe", home_country="US"
    )
    account = Account(customer=customer, account_type="checking", balance=Decimal("500.00"))
    transactions = [
        Transaction(
            account=account,
            amount=Decimal("25.00") * (i + 1),
            transaction_type="purchase",
            channel="pos",
            merchant_name="Safeway",
            merchant_category="grocery",
            city="Tempe",
            country="US",
            occurred_at=BASE + timedelta(hours=i),
        )
        for i in range(5)
    ]
    db.add(customer)
    db.flush()
    flag = FraudFlag(transaction_id=transactions[4].id, fraud_score=0.91, model_version="xgb-test")
    db.add(flag)
    db.flush()
    return {"customer": customer, "account": account, "transactions": transactions, "flag": flag}
