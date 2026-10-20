import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.money import MAX_INTEREST_RATE, MAX_NUMERIC_12_2, MAX_NUMERIC_14_2

_EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


def _normalize_sender(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip().lower() or None


class DebtBase(BaseModel):
    bank_name: str = Field(..., min_length=1, max_length=128)
    total_amount: Decimal = Field(..., le=MAX_NUMERIC_14_2)
    interest_rate: Decimal | None = Field(default=None, ge=0, le=MAX_INTEREST_RATE)
    minimum_payment: Decimal | None = Field(default=None, ge=0, le=MAX_NUMERIC_12_2)
    # Due date of the next payment. Typed by the user for cards without a
    # statement email (Banco de Bogotá); statement emails refresh it.
    payment_due_date: date | None = None
    # Credit-card email link: sender + one of GET /debts/card-formats.
    email_sender: str | None = Field(default=None, max_length=255, pattern=_EMAIL_PATTERN)
    email_format: str | None = Field(default=None, max_length=32)
    card_last_digits: str | None = Field(default=None, pattern=r"^\d{4}$")

    _sender = field_validator("email_sender", mode="before")(_normalize_sender)


class DebtCreate(DebtBase):
    pass


class DebtUpdate(BaseModel):
    bank_name: str | None = None
    total_amount: Decimal | None = Field(default=None, le=MAX_NUMERIC_14_2)
    interest_rate: Decimal | None = Field(default=None, ge=0, le=MAX_INTEREST_RATE)
    minimum_payment: Decimal | None = Field(default=None, ge=0, le=MAX_NUMERIC_12_2)
    payment_due_date: date | None = None
    email_sender: str | None = Field(default=None, max_length=255, pattern=_EMAIL_PATTERN)
    email_format: str | None = Field(default=None, max_length=32)
    card_last_digits: str | None = Field(default=None, pattern=r"^\d{4}$")

    _sender = field_validator("email_sender", mode="before")(_normalize_sender)


class DebtOut(DebtBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email_linked_at: datetime | None = None
    created_at: datetime


class CardFormatOut(BaseModel):
    key: str
    label: str
    default_sender: str | None


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
