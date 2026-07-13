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


class DebtPayoffOut(BaseModel):
    name: str
    payoff_month: int | None
    interest_paid: Decimal


class StrategyResultOut(BaseModel):
    strategy: str
    months_to_free: int | None
    total_interest: Decimal
    total_paid: Decimal
    payoff_order: list[str]
    per_debt: list[DebtPayoffOut]
    converges: bool


class StrategyComparisonOut(BaseModel):
    avalanche: StrategyResultOut
    snowball: StrategyResultOut
    interest_saved_by_avalanche: Decimal
    months_saved_by_avalanche: int | None
    recommended: str
