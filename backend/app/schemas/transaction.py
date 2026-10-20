import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

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

    _occurred_at = field_validator("occurred_at")(check_expense_date)


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
