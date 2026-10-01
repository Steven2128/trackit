import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


# --- Income sources ---


class IncomeSourceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    amount: Decimal = Field(..., gt=0)
    expected_day: int = Field(..., ge=1, le=31)


class IncomeSourceCreate(IncomeSourceBase):
    pass


class IncomeSourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    amount: Decimal | None = Field(default=None, gt=0)
    expected_day: int | None = Field(default=None, ge=1, le=31)


class IncomeSourceOut(IncomeSourceBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime


# --- Planned payments ---


class PlannedPaymentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    amount: Decimal = Field(..., gt=0)
    due_day: int | None = Field(default=None, ge=1, le=31)
    grace_days: int = Field(default=0, ge=0, le=60)
    is_debt_payment: bool = False


class PlannedPaymentCreate(PlannedPaymentBase):
    pass


class PlannedPaymentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    amount: Decimal | None = Field(default=None, gt=0)
    due_day: int | None = Field(default=None, ge=1, le=31)
    grace_days: int | None = Field(default=None, ge=0, le=60)
    is_debt_payment: bool | None = None
    # "YYYY-MM" to check off for that month; null to un-check.
    paid_month: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")


class PlannedPaymentOut(PlannedPaymentBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    paid_month: str | None


# --- Cash flow ---


class UpcomingPaymentOut(BaseModel):
    id: uuid.UUID | None
    name: str
    amount: Decimal
    deadline: date | None
    days_left: int | None
    is_debt_payment: bool
    is_paid: bool


class CashFlowResponse(BaseModel):
    monthly_income: Decimal
    monthly_committed: Decimal
    available: Decimal
    next_income_date: date | None
    next_income_name: str | None
    next_income_amount: Decimal | None
    upcoming: list[UpcomingPaymentOut]
    checklist: list[UpcomingPaymentOut]
