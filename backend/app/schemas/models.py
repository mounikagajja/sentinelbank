from datetime import datetime
from decimal import Decimal

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
