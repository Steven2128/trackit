import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.transaction import TransactionType


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


class TransactionUpdate(BaseModel):
    # Partial update — only fields the client actually sent are applied
    # (checked via model_fields_set in the route). None clears the field.
    category: str | None = None
    merchant: str | None = None
    note: str | None = None


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
