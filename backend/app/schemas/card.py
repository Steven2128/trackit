import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class CardPurchaseOut(BaseModel):
    id: uuid.UUID
    occurred_at: datetime
    merchant: str | None
    category: str | None
    amount: Decimal


class InstallmentPlanOut(BaseModel):
    """A purchase split in installments, as of the last statement."""

    description: str
    purchased_on: date
    amount: Decimal
    installment: int  # the one the last statement billed
    installments: int
    billed: Decimal | None
    pending: Decimal  # capital still to bill
    next_amount: Decimal  # what the next statement bills (0 = finished)
    remaining: int  # installments left after the last statement


class StatementSummaryOut(BaseModel):
    id: uuid.UUID
    period_start: date | None
    period_end: date
    due_date: date | None
    minimum_payment: Decimal | None
    total_payment: Decimal | None
    purchases_total: Decimal
    payments_total: Decimal
    lines_count: int


class StatementLineOut(BaseModel):
    position: int
    posted_on: date
    description: str
    amount: Decimal
    billed: Decimal | None
    installment: int | None
    installments: int | None
    pending: Decimal | None


class StatementDetailOut(StatementSummaryOut):
    lines: list[StatementLineOut]


class CardOut(BaseModel):
    debt_id: uuid.UUID
    name: str
    balance: Decimal
    credit_limit: Decimal | None
    available: Decimal | None
    # The statement to pay now.
    minimum_payment: Decimal | None
    payment_due_date: date | None
    paid_since_cutoff: Decimal
    cutoff_date: date | None
    # The one being built: purchases since the cut-off + known installments.
    next_cutoff_date: date | None
    next_due_date: date | None
    purchases_since_cutoff: list[CardPurchaseOut]
    purchases_since_cutoff_total: Decimal
    next_installments: Decimal
    next_statement_estimate: Decimal
    installment_plans: list[InstallmentPlanOut]
    statements: list[StatementSummaryOut]
