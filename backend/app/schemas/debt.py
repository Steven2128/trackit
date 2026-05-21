import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class DebtBase(BaseModel):
    bank_name: str = Field(..., min_length=1, max_length=128)
    total_amount: Decimal
    interest_rate: Decimal | None = None
    minimum_payment: Decimal | None = None


class DebtCreate(DebtBase):
    pass


class DebtUpdate(BaseModel):
    bank_name: str | None = None
    total_amount: Decimal | None = None
    interest_rate: Decimal | None = None
    minimum_payment: Decimal | None = None


class DebtOut(DebtBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
