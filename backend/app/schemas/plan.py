import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.money import MAX_NUMERIC_14_2

# --- Income sources ---


class IncomeSourceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    amount: Decimal = Field(..., gt=0, le=MAX_NUMERIC_14_2)
    expected_day: int = Field(..., ge=1, le=31)


class IncomeSourceCreate(IncomeSourceBase):
    pass


class IncomeSourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    amount: Decimal | None = Field(default=None, gt=0, le=MAX_NUMERIC_14_2)
    expected_day: int | None = Field(default=None, ge=1, le=31)


class IncomeSourceOut(IncomeSourceBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime


# --- Planned payments ---


class PlannedPaymentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    amount: Decimal = Field(..., gt=0, le=MAX_NUMERIC_14_2)
    due_day: int | None = Field(default=None, ge=1, le=31)
    grace_days: int = Field(default=0, ge=0, le=60)
    is_debt_payment: bool = False
    # One-off (money owed to a friend): due once on this date.
    due_date: date | None = None


class PlannedPaymentCreate(PlannedPaymentBase):
    pass


class PlannedPaymentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    amount: Decimal | None = Field(default=None, gt=0, le=MAX_NUMERIC_14_2)
    due_day: int | None = Field(default=None, ge=1, le=31)
    grace_days: int | None = Field(default=None, ge=0, le=60)
    is_debt_payment: bool | None = None
    due_date: date | None = None
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


# --- Cash position by fortnight (GET /cashflow/position) ---


class PositionLineOut(BaseModel):
    name: str
    amount: Decimal  # still owed
    estimated: bool
    due: date | None
    total: Decimal  # what the due date asks for; paid = total − amount
    # "planned:<id>:<due>" / "debt:<id>:<due>" — what POST
    # /obligation-payments needs to pay it.
    ref: str | None


class PositionWindowOut(BaseModel):
    start: date
    end: date | None  # exclusive; None = open until the horizon
    income: Decimal
    income_names: list[str]
    obligations: list[PositionLineOut]
    essentials: Decimal
    balance_after: Decimal


class PositionDeficitOut(BaseModel):
    window_start: date
    amount: Decimal
    obligations: list[str]


class CashPositionResponse(BaseModel):
    """How much of today's money is really free (services/cash_position.py).

    ``status``: confirmed | provisional (uses estimates) | indeterminate
    (something that matters is unknown — see ``missing``).
    """

    status: str
    today: date
    horizon_end: date
    pay_due_on_payday: bool
    balance: Decimal
    held_for_others: Decimal
    own: Decimal
    due_before_next_income: Decimal
    essentials_until_next_income: Decimal
    reserve_for_later: Decimal
    free: Decimal
    spendable_now: Decimal
    windows: list[PositionWindowOut]
    deficit: PositionDeficitOut | None
    missing: list[str]
    estimated: list[str]
    late_incomes: list[str]
    overdue: list[str]
    no_plan: list[str]
    notes: list[str]


# --- Money held for others / payments toward a due date ---


class FundHoldIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    amount: Decimal = Field(..., gt=0, le=MAX_NUMERIC_14_2)


class FundHoldUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    amount: Decimal | None = Field(default=None, gt=0, le=MAX_NUMERIC_14_2)


class FundHoldOut(FundHoldIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime


class ObligationPaymentIn(BaseModel):
    """Exactly one of planned_payment_id / debt_id."""

    planned_payment_id: uuid.UUID | None = None
    debt_id: uuid.UUID | None = None
    due_date: date
    amount: Decimal = Field(..., gt=0, le=MAX_NUMERIC_14_2)
    paid_on: date | None = None  # default: today (local)
    # Paid in cash: also logs the cash expense, so the balance drops with it.
    # Bank payments arrive by email on their own.
    from_cash: bool = False


class ObligationPaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    planned_payment_id: uuid.UUID | None
    debt_id: uuid.UUID | None
    due_date: date
    amount: Decimal
    paid_on: date
    transaction_id: uuid.UUID | None
    created_at: datetime
