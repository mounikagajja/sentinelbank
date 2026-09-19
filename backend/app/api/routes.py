from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.security import AnalystUser, CurrentUser
from backend.app.db.session import get_db
from backend.app.models import Account, Customer, FraudFlag, Transaction
from backend.app.schemas.models import (
    AccountOut,
    AccountStatusUpdate,
    CustomerOut,
    FlaggedPage,
    FlaggedTransactionOut,
    FlagStatusUpdate,
    FraudFlagOut,
    TransactionOut,
    TransactionPage,
)

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]

FLAG_STATUSES = ("open", "confirmed", "dismissed")


@router.get("/customers/{customer_id}", response_model=CustomerOut, tags=["customers"])
def get_customer(customer_id: int, db: DbSession, user: CurrentUser) -> Customer:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.get(
    "/customers/{customer_id}/accounts", response_model=list[AccountOut], tags=["customers"]
)
def list_customer_accounts(customer_id: int, db: DbSession, user: CurrentUser) -> list[Account]:
    if db.get(Customer, customer_id) is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return list(db.scalars(select(Account).where(Account.customer_id == customer_id)))


@router.get("/accounts/{account_id}", response_model=AccountOut, tags=["accounts"])
def get_account(account_id: int, db: DbSession, user: CurrentUser) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.get(
    "/accounts/{account_id}/transactions", response_model=TransactionPage, tags=["accounts"]
)
def list_account_transactions(
    account_id: int,
    db: DbSession,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TransactionPage:
    if db.get(Account, account_id) is None:
        raise HTTPException(status_code=404, detail="Account not found")

    condition = Transaction.account_id == account_id
    total = db.scalar(select(func.count()).select_from(Transaction).where(condition))
    rows = db.scalars(
        select(Transaction)
        .where(condition)
        .order_by(Transaction.occurred_at.desc(), Transaction.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return TransactionPage(
        total=total,
        limit=limit,
        offset=offset,
        items=[TransactionOut.model_validate(row) for row in rows],
    )


@router.get("/transactions/{transaction_id}", response_model=TransactionOut, tags=["transactions"])
def get_transaction(transaction_id: int, db: DbSession, user: CurrentUser) -> Transaction:
    transaction = db.get(Transaction, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


@router.get("/flags", response_model=FlaggedPage, tags=["flags"])
def list_flags(
    db: DbSession,
    user: CurrentUser,
    status: Annotated[str | None, Query()] = None,
    min_score: Annotated[float, Query(ge=0.0, le=1.0)] = 0.0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> FlaggedPage:
    if status is not None and status not in FLAG_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {FLAG_STATUSES}")

    query = select(FraudFlag, Transaction).join(
        Transaction, Transaction.id == FraudFlag.transaction_id
    )
    count_query = select(func.count()).select_from(FraudFlag)

    if status is not None:
        query = query.where(FraudFlag.status == status)
        count_query = count_query.where(FraudFlag.status == status)
    if min_score > 0.0:
        query = query.where(FraudFlag.fraud_score >= min_score)
        count_query = count_query.where(FraudFlag.fraud_score >= min_score)

    total = db.scalar(count_query)
    rows = db.execute(
        query.order_by(FraudFlag.created_at.desc(), FraudFlag.id.desc()).limit(limit).offset(offset)
    ).all()

    return FlaggedPage(
        total=total,
        limit=limit,
        offset=offset,
        items=[
            FlaggedTransactionOut(
                flag=FraudFlagOut.model_validate(flag),
                transaction=TransactionOut.model_validate(transaction),
            )
            for flag, transaction in rows
        ],
    )


@router.get("/flags/{flag_id}", response_model=FlaggedTransactionOut, tags=["flags"])
def get_flag(flag_id: int, db: DbSession, user: CurrentUser) -> FlaggedTransactionOut:
    flag = db.get(FraudFlag, flag_id)
    if flag is None:
        raise HTTPException(status_code=404, detail="Flag not found")
    transaction = db.get(Transaction, flag.transaction_id)
    return FlaggedTransactionOut(
        flag=FraudFlagOut.model_validate(flag),
        transaction=TransactionOut.model_validate(transaction),
    )


@router.patch("/accounts/{account_id}/status", response_model=AccountOut, tags=["accounts"])
def update_account_status(
    account_id: int, payload: AccountStatusUpdate, db: DbSession, user: AnalystUser
) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.status == payload.status:
        raise HTTPException(status_code=409, detail=f"Account is already {payload.status}")

    account.status = payload.status
    db.flush()
    return account


@router.patch("/flags/{flag_id}/status", response_model=FraudFlagOut, tags=["flags"])
def update_flag_status(
    flag_id: int, payload: FlagStatusUpdate, db: DbSession, user: AnalystUser
) -> FraudFlag:
    flag = db.get(FraudFlag, flag_id)
    if flag is None:
        raise HTTPException(status_code=404, detail="Flag not found")
    if flag.status != "open":
        raise HTTPException(status_code=409, detail=f"Flag was already {flag.status}")

    flag.status = payload.status
    flag.reviewed_at = datetime.now(UTC)
    db.flush()
    return flag
