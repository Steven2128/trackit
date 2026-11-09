import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.transaction import TransactionType
from app.schemas.money import MAX_NUMERIC_12_2

# Tolerates a phone clock a few minutes ahead of the server's.
_CLOCK_SKEW = timedelta(minutes=5)


def check_expense_date(value: datetime | None) -> datetime | None:
    """A typed-in expense happened at a known instant, never in the future.
    Naive datetimes are rejected: their local day would be ambiguous."""
    if value is None:
        return value
    if value.tzinfo is None:
        raise ValueError("occurred_at needs a timezone")
    if value > datetime.now(timezone.utc) + _CLOCK_SKEW:
        raise ValueError("occurred_at is in the future")
    return value


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    amount: Decimal
    merchant: str | None
    category: str | None
    transaction_type: TransactionType
    currency: str
    card_last_digits: str | None
    occurred_at: datetime
    note: str | None
    # Set on credit-card purchases/payments read from a debt's email sender.
    debt_id: uuid.UUID | None = None
    # Account the money moved in ("davivienda", "nequi", "card", "cash", ...).
    source: str | None = None
    # Part of a debit someone else covers; spending counts amount - this.
    shared_amount: Decimal | None = None
    # Who it's shared with / paid back by (services/contact_balance.py).
    contact_id: uuid.UUID | None = None
    # Typed in by the user (no email): amount, date and deletion editable.
    manual: bool = False


class TransactionUpdate(BaseModel):
    # Partial update — only fields the client actually sent are applied
    # (checked via model_fields_set in the route). None clears the field.
    category: str | None = None
    merchant: str | None = None
    note: str | None = None
    # Only for typed-in cash expenses (source="cash"); bank rows keep the
    # amount from their email, the route rejects it there.
    amount: Decimal | None = Field(default=None, gt=0, le=MAX_NUMERIC_12_2)
    # Also cash-only: the day the user actually spent it.
    occurred_at: datetime | None = None
    # Debits only: the part someone else pays back. None or 0 = not shared.
    shared_amount: Decimal | None = Field(default=None, ge=0, le=MAX_NUMERIC_12_2)
    # Debits only: the hand-entered debt this paid (a family loan, a bank
    # loan without emails). Lowers that debt's balance; None unlinks it.
    debt_id: uuid.UUID | None = None
    # Who it's shared with or paid back by; None clears it.
    contact_id: uuid.UUID | None = None

    _occurred_at = field_validator("occurred_at")(check_expense_date)


class ManualMovementIn(BaseModel):
    """A movement with no email behind it: a payback by "llave", money lent,
    or an expense a contact paid.

    ``account`` is where the money moved ("davivienda", "nequi", "cash"), or
    "contact" for an expense the contact paid — then it must be a debit,
    ``contact_id`` is required and ``shared_amount`` is their part (the rest
    is the user's spending)."""

    account: Literal["davivienda", "nequi", "cash", "contact"]
    transaction_type: TransactionType
    amount: Decimal = Field(..., gt=0, le=MAX_NUMERIC_12_2)
    merchant: str = Field(..., min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=64)
    contact_id: uuid.UUID | None = None
    shared_amount: Decimal | None = Field(default=None, ge=0, le=MAX_NUMERIC_12_2)
    note: str | None = Field(default=None, max_length=500)
    occurred_at: datetime | None = None

    _occurred_at = field_validator("occurred_at")(check_expense_date)


class ContactBalance(BaseModel):
    contact_id: uuid.UUID
    name: str
    # > 0: they owe the user; < 0: the user owes them.
    balance: Decimal


class SharedSummary(BaseModel):
    """Running balance of shared expenses: what others' parts added up to,
    what they paid back (reimbursement credits) and what's still owed."""

    covered_for_others: Decimal
    reimbursed: Decimal
    pending: Decimal
    # Per contact; the three totals above are what isn't assigned to anyone.
    people: list[ContactBalance] = []
    # Latest shared debits and reimbursement credits, newest first.
    items: list[TransactionOut]


class TransactionListResponse(BaseModel):
    items: list[TransactionOut]
    total: int
    limit: int
    offset: int


class CategorySummaryItem(BaseModel):
    category: str | None
    total: Decimal
    count: int


class TransactionSummary(BaseModel):
    month: str
    total_spent: Decimal
    total_received: Decimal
    by_category: list[CategorySummaryItem]
    transaction_count: int
