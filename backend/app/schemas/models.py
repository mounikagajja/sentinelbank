from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    home_city: str
    home_country: str


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    account_type: str
    balance: Decimal
    status: str
    created_at: datetime


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    amount: Decimal
    transaction_type: str
    channel: str
    merchant_name: str
    merchant_category: str
    city: str
    country: str
    occurred_at: datetime
    is_fraud: bool


class FraudFlagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    transaction_id: int
    fraud_score: float
    model_version: str
    status: str
    created_at: datetime
    reviewed_at: datetime | None


class FlaggedTransactionOut(BaseModel):
    flag: FraudFlagOut
    transaction: TransactionOut


class Page(BaseModel):
    total: int
    limit: int
    offset: int


class TransactionPage(Page):
    items: list[TransactionOut]


class FlaggedPage(Page):
    items: list[FlaggedTransactionOut]


class PaginationParams(BaseModel):
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class AccountStatusUpdate(BaseModel):
    status: Literal["active", "frozen"]
    reason: str = Field(min_length=3, max_length=200)


class FlagStatusUpdate(BaseModel):
    status: Literal["confirmed", "dismissed"]
    note: str | None = Field(default=None, max_length=500)


class FeatureContribution(BaseModel):
    feature: str
    value: float
    contribution: float
    direction: str


class FlagExplanation(BaseModel):
    flag_id: int
    transaction_id: int
    fraud_score: float
    model_version: str
    baseline_score: float
    top_contributions: list[FeatureContribution]
