"""Projected monthly cash flow: fixed income - fixed obligations = available.

Pure, DB-free core (same shape as subscription_detector / debt_strategy).
The DB wrapper lives in `app/api/routes/plan.py` (`GET /cashflow`).

Also derives the two views the mobile "Plan" screen needs:
- upcoming due dates per obligation (this month or next, honoring grace days)
- the pay-first checklist: debts first, then nearest due date — the order
  the user should pay things the moment income lands.
"""

from __future__ import annotations

import calendar
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal


@dataclass
class IncomeLike:
    name: str
    amount: Decimal
    expected_day: int  # 1-31


@dataclass
class PaymentLike:
    name: str
    amount: Decimal
    due_day: int | None  # 1-31; None = no deadline (pure apartado)
    grace_days: int
    is_debt_payment: bool
    id: uuid.UUID | None = None
    is_paid: bool = False  # checked off for the current month


@dataclass
class UpcomingPayment:
    name: str
    amount: Decimal
    deadline: date | None  # due date + grace; None when due_day is None
    days_left: int | None
    is_debt_payment: bool
    id: uuid.UUID | None = None
    is_paid: bool = False


@dataclass
class CashFlowResult:
    monthly_income: Decimal
    monthly_committed: Decimal
    available: Decimal
    next_income_date: date | None
    next_income_name: str | None
    next_income_amount: Decimal | None
    upcoming: list[UpcomingPayment]  # sorted by deadline (None last)
    checklist: list[UpcomingPayment]  # pay-first order: debts, then deadline


def _clamp_day(year: int, month: int, day: int) -> date:
    """Day 31 in a 30-day month lands on the last day, not next month."""
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last))


def _next_occurrence(day: int, today: date) -> date:
    """Next date (today or later) whose day-of-month is `day`."""
    this_month = _clamp_day(today.year, today.month, day)
    if this_month >= today:
        return this_month
    if today.month == 12:
        return _clamp_day(today.year + 1, 1, day)
    return _clamp_day(today.year, today.month + 1, day)


def compute_cash_flow(
    incomes: list[IncomeLike],
    payments: list[PaymentLike],
    today: date,
) -> CashFlowResult:
    monthly_income = sum((i.amount for i in incomes), Decimal("0"))
    monthly_committed = sum((p.amount for p in payments), Decimal("0"))

    next_income: tuple[date, IncomeLike] | None = None
    for income in incomes:
        occurrence = _next_occurrence(income.expected_day, today)
        if next_income is None or occurrence < next_income[0]:
            next_income = (occurrence, income)

    upcoming: list[UpcomingPayment] = []
    for p in payments:
        if p.due_day is None:
            upcoming.append(
                UpcomingPayment(
                    name=p.name,
                    amount=p.amount,
                    deadline=None,
                    days_left=None,
                    is_debt_payment=p.is_debt_payment,
                    id=p.id,
                    is_paid=p.is_paid,
                )
            )
            continue
        due = _next_occurrence(p.due_day, today)
        deadline = due + timedelta(days=p.grace_days)
        upcoming.append(
            UpcomingPayment(
                name=p.name,
                amount=p.amount,
                deadline=deadline,
                days_left=(deadline - today).days,
                is_debt_payment=p.is_debt_payment,
                id=p.id,
                is_paid=p.is_paid,
            )
        )

    far_future = date.max
    upcoming.sort(key=lambda u: u.deadline or far_future)
    # Checked-off items sink to the bottom so the unpaid ones stay on top.
    checklist = sorted(
        upcoming,
        key=lambda u: (u.is_paid, not u.is_debt_payment, u.deadline or far_future),
    )

    return CashFlowResult(
        monthly_income=monthly_income,
        monthly_committed=monthly_committed,
        available=monthly_income - monthly_committed,
        next_income_date=next_income[0] if next_income else None,
        next_income_name=next_income[1].name if next_income else None,
        next_income_amount=next_income[1].amount if next_income else None,
        upcoming=upcoming,
        checklist=checklist,
    )
