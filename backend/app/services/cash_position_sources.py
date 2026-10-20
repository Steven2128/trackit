"""Turn what the app stores into cash_position inputs.

Pure: the route (``GET /cashflow/position``) loads rows and passes them in.

- balance: the computed account balances (services/net_worth.py), minus
  ``fund_holds`` (money kept for someone else);
- expected income: each ``income_sources`` row on its day of each month,
  weekend paydays on the Friday before, skipped once a matching deposit
  shows up in the movements;
- obligations: each ``planned_payments`` row — monthly on ``due_day``, or
  once on ``due_date`` (money owed to a friend) — and each debt's next due
  date for the larger of its minimum and what the user plans to pay.
  What's already paid toward a due date = ``obligation_payments`` for it
  (partial or ahead); the old monthly check-off still counts as paid in
  full, and card payments read from email count when nothing was recorded.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Protocol, Sequence

from app.services.cash_position import (
    AmountStatus,
    ExpectedIncome,
    Hold,
    Obligation,
    PositionInputs,
    fortnight_bounds,
    payday,
)

ZERO = Decimal("0")
# A deposit counts as the expected one if it lands this close to its day
# and is at least this share of the expected amount.
RECEIVED_DAYS_BEFORE = 5
RECEIVED_DAYS_AFTER = 4
RECEIVED_MIN_SHARE = Decimal("0.90")
# Only deposits expected this far back are still awaited (late), not lost.
LATE_LOOKBACK_DAYS = 5
# Card payments this long before a due date count against that statement.
STATEMENT_WINDOW_DAYS = 35



class IncomeSourceLike(Protocol):
    name: str
    amount: Decimal
    expected_day: int


class PlannedPaymentLike(Protocol):
    id: object
    name: str
    amount: Decimal
    due_day: int | None
    due_date: date | None
    paid_month: str | None


class DebtLike(Protocol):
    id: object
    bank_name: str
    minimum_payment: Decimal | None
    planned_payment: Decimal | None
    payment_due_date: date | None
    email_format: str | None


class FundHoldLike(Protocol):
    name: str
    amount: Decimal


@dataclass(frozen=True)
class Credit:
    """A deposit already in the movements (local date)."""

    on: date
    amount: Decimal


@dataclass(frozen=True)
class DebtPayment:
    """A card payment read from email (debt_payment movement)."""

    debt_id: object
    on: date
    amount: Decimal


@dataclass(frozen=True)
class PaymentRecord:
    """An obligation_payments row: money put toward one due date."""

    due_date: date
    amount: Decimal
    planned_payment_id: object = None
    debt_id: object = None


def _recorded(records: Sequence[PaymentRecord], due: date, *, planned=None, debt=None) -> Decimal:
    return sum(
        (
            r.amount
            for r in records
            if r.due_date == due
            and (
                (planned is not None and r.planned_payment_id == planned)
                or (debt is not None and r.debt_id == debt)
            )
        ),
        ZERO,
    )


def default_horizon(today: date) -> date:
    """Through the payday after the next one: on the 19th → the 5th, on
    the 20th → the 20th of next month."""
    return fortnight_bounds(fortnight_bounds(today)[1])[1]


def _months(start: date, end: date) -> list[tuple[int, int]]:
    out = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def expected_incomes(
    sources: Sequence[IncomeSourceLike],
    credits: Sequence[Credit],
    today: date,
    horizon_end: date,
) -> list[ExpectedIncome]:
    """Expected deposits still to come. A deposit near the day and close in
    amount confirms one (and only one) expected income; the closest amounts
    pair first, so a 1.050.905 bonus doesn't pass for a 1.136.548 payroll
    paid the same week."""
    start = today - timedelta(days=LATE_LOOKBACK_DAYS + RECEIVED_DAYS_BEFORE)
    expected: list[tuple[date, IncomeSourceLike]] = []
    for y, m in _months(start, horizon_end):
        for src in sources:
            on = payday(y, m, src.expected_day)
            if today - timedelta(days=LATE_LOOKBACK_DAYS) <= on <= horizon_end:
                expected.append((on, src))

    pairs = []
    for ei, (on, src) in enumerate(expected):
        for ci, c in enumerate(credits):
            near = (
                on - timedelta(days=RECEIVED_DAYS_BEFORE)
                <= c.on
                <= on + timedelta(days=RECEIVED_DAYS_AFTER)
            )
            gap = abs(c.amount - src.amount) / src.amount
            if near and gap <= 1 - RECEIVED_MIN_SHARE:
                pairs.append((gap, abs((c.on - on).days), ei, ci))
    received: set[int] = set()
    used: set[int] = set()
    for _gap, _days, ei, ci in sorted(pairs):
        if ei not in received and ci not in used:
            received.add(ei)
            used.add(ci)

    return [
        ExpectedIncome(f"{src.name} ({on.day}/{on.month})", src.amount, on)
        for ei, (on, src) in sorted(enumerate(expected), key=lambda e: e[1][0])
        if ei not in received
    ]


def planned_obligations(
    payments: Sequence[PlannedPaymentLike],
    today: date,
    horizon_end: date,
    records: Sequence[PaymentRecord] = (),
) -> list[Obligation]:
    out = []
    current = f"{today.year:04d}-{today.month:02d}"
    for p in payments:
        if p.due_date is not None:
            # One-off: the check-off (any month) or recorded payments settle it.
            due = p.due_date
            if due > horizon_end:
                continue
            paid = p.amount if p.paid_month else _recorded(records, due, planned=p.id)
            if paid >= p.amount:
                continue
            out.append(
                Obligation(p.name, due, p.amount, paid=paid, ref=f"planned:{p.id}:{due}")
            )
            continue
        if p.due_day is None:
            paid = p.amount if p.paid_month == current else ZERO
            out.append(Obligation(p.name, None, p.amount, paid=paid, ref=f"planned:{p.id}:"))
            continue
        for y, m in _months(today, horizon_end):
            due = date(y, m, min(p.due_day, calendar.monthrange(y, m)[1]))
            if due > horizon_end:
                continue
            checked = p.amount if p.paid_month == f"{y:04d}-{m:02d}" else ZERO
            paid = max(checked, _recorded(records, due, planned=p.id))
            # Past due this month and not fully paid: still owed (overdue).
            if due < today and paid >= p.amount:
                continue
            out.append(
                Obligation(
                    f"{p.name} ({due.day}/{due.month})",
                    due,
                    p.amount,
                    paid=paid,
                    ref=f"planned:{p.id}:{due}",
                )
            )
    return out


def _add_month(d: date) -> date:
    y, m = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def debt_obligations(
    debts: Sequence[DebtLike],
    payments: Sequence[DebtPayment],
    today: date,
    horizon_end: date | None = None,
    records: Sequence[PaymentRecord] = (),
) -> list[Obligation]:
    """Each debt's due dates in the horizon, for max(minimum, planned).

    Cards read by email: only the latest statement's date (an old one means
    the next statement hasn't arrived). Debts typed by hand (no email): the
    date repeats monthly — rolled past dates are flagged as estimated, the
    user should confirm them against the statement.
    """
    horizon_end = horizon_end or today
    out = []
    for d in debts:
        amount = max(d.minimum_payment or ZERO, d.planned_payment or ZERO)
        if amount == 0:
            continue
        planned = d.planned_payment is not None and d.planned_payment > (d.minimum_payment or 0)
        name = f"{'Abono' if planned else 'Mínimo'} {d.bank_name}"
        due = d.payment_due_date
        if due is None:
            out.append(Obligation(name, None, amount, ref=f"debt:{d.id}:"))
            continue
        dues = [due]
        rolled = False
        if d.email_format is None:
            while dues[-1] < today:
                dues[-1] = _add_month(dues[-1])
                rolled = True
            while _add_month(dues[-1]) <= horizon_end:
                dues.append(_add_month(dues[-1]))
        elif due < today:
            continue  # an old statement: the next one hasn't arrived yet
        for i, when in enumerate(dues):
            recorded = _recorded(records, when, debt=d.id)
            if recorded:
                paid = recorded
            else:
                since = when - timedelta(days=STATEMENT_WINDOW_DAYS)
                paid = sum(
                    (p.amount for p in payments if p.debt_id == d.id and since <= p.on <= when),
                    ZERO,
                )
            out.append(
                Obligation(
                    name,
                    when,
                    amount,
                    status=AmountStatus.estimated if rolled or i else AmountStatus.confirmed,
                    paid=paid,
                    ref=f"debt:{d.id}:{when}",
                )
            )
    return out


def holds(rows: Sequence[FundHoldLike]) -> tuple[Hold, ...]:
    return tuple(Hold(r.name, r.amount) for r in rows)


def build_inputs(
    *,
    today: date,
    horizon_end: date,
    balance: Decimal,
    income_sources: Sequence[IncomeSourceLike],
    credits: Sequence[Credit],
    planned_payments: Sequence[PlannedPaymentLike],
    debts: Sequence[DebtLike],
    debt_payments: Sequence[DebtPayment],
    pay_due_on_payday: bool,
    fund_holds: Sequence[FundHoldLike] = (),
    records: Sequence[PaymentRecord] = (),
) -> PositionInputs:
    return PositionInputs(
        today=today,
        horizon_end=horizon_end,
        balance=balance,
        holds=holds(fund_holds),
        incomes=tuple(expected_incomes(income_sources, credits, today, horizon_end)),
        obligations=(
            *planned_obligations(planned_payments, today, horizon_end, records),
            *debt_obligations(debts, debt_payments, today, horizon_end, records),
        ),
        pay_due_on_payday=pay_due_on_payday,
    )
