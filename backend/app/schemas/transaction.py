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
    created_at: datetime


class TransactionSummary(BaseModel):
    total_debit: Decimal = Decimal("0")
    total_credit: Decimal = Decimal("0")
    transaction_count: int = 0
