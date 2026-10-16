import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.account import AccountKind
from app.schemas.money import MAX_NUMERIC_12_2, MAX_NUMERIC_14_2


class AccountUpsert(BaseModel):
    """Set (or reset) an account's starting point: today's real balance."""

    opening_balance: Decimal = Field(..., ge=0, le=MAX_NUMERIC_14_2)
    name: str | None = Field(default=None, min_length=1, max_length=64)


class ReconcileIn(BaseModel):
    balance: Decimal = Field(
        ..., ge=-MAX_NUMERIC_14_2, le=MAX_NUMERIC_14_2,
        description="Real balance shown by the bank right now.",
    )


class AccountOut(BaseModel):
    id: uuid.UUID
    kind: AccountKind
    name: str
    opening_balance: Decimal
    opening_at: datetime
    balance: Decimal
    last_reconciled_at: datetime | None
    # Σ adjustments this local month: money that moved without an email.
    unexplained_this_month: Decimal


class NetWorthOut(BaseModel):
    accounts: list[AccountOut]
    total_assets: Decimal
    total_debt: Decimal
    net_worth: Decimal
    unexplained_this_month: Decimal


class ReconcileOut(BaseModel):
    computed_balance: Decimal
    reported_balance: Decimal
    difference: Decimal


class CashExpenseIn(BaseModel):
    amount: Decimal = Field(..., gt=0, le=MAX_NUMERIC_12_2)
    merchant: str = Field(..., min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=64)
    occurred_at: datetime | None = None
