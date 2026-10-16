import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.transaction import TransactionType
from app.schemas.money import MAX_NUMERIC_12_2


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
