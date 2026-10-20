"""Turn what the app already stores into cash_position inputs (stage 2).

Pure: the route (``GET /cashflow/position``) loads rows and passes them in.
No new tables yet, so this reads only what exists:

- balance: the computed account balances (services/net_worth.py);
- expected income: each ``income_sources`` row on its day of each month,
  weekend paydays on the Friday before, skipped once a matching deposit
  shows up in the movements;
- obligations: each ``planned_payments`` row on its ``due_day`` (the
  monthly check-off marks the current month's one as paid) and the latest
  statement of each debt (minimum + due date), minus the card payments
  already linked to that debt.

Not there yet (needs schema, stage 3): money held for others, one-off
obligations and partial payments of a planned payment. ``NOTES`` says so in
the response instead of pretending.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Protocol, Sequence

from app.services.cash_position import (
    ExpectedIncome,
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

NOTES = [
    "Todavía no se descuenta la plata de terceros (por ejemplo, la de tu hermano).",
    "Todavía no entran las deudas de una sola vez (amigos, familia) ni los pagos parciales.",
]


class IncomeSourceLike(Protocol):
    name: str
    amount: Decimal
    expected_day: int


class PlannedPaymentLike(Protocol):
    name: str
    amount: Decimal
    due_day: int | None
    paid_month: str | None


class DebtLike(Protocol):
    id: object
    bank_name: str
    minimum_payment: Decimal | None
    payment_due_date: date | None


@dataclass(frozen=True)
class Credit:
    """A deposit already in the movements (local date)."""

    on: date
    amount: Decimal


@dataclass(frozen=True)
class DebtPayment:
    debt_id: object
    on: date
    amount: Decimal


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
    payments: Sequence[PlannedPaymentLike], today: date, horizon_end: date
) -> list[Obligation]:
    out = []
    current = f"{today.year:04d}-{today.month:02d}"
    for p in payments:
        if p.due_day is None:
            paid = p.amount if p.paid_month == current else ZERO
            out.append(Obligation(p.name, None, p.amount, paid=paid))
            continue
        for y, m in _months(today, horizon_end):
            due = date(y, m, min(p.due_day, calendar.monthrange(y, m)[1]))
            month = f"{y:04d}-{m:02d}"
            if due > horizon_end:
                continue
            paid = p.amount if p.paid_month == month else ZERO
            # Past due this month and not checked off: still owed (overdue).
            if due < today and paid == p.amount:
                continue
            out.append(Obligation(f"{p.name} ({due.day}/{due.month})", due, p.amount, paid=paid))
    return out


def debt_obligations(
    debts: Sequence[DebtLike], payments: Sequence[DebtPayment], today: date
) -> list[Obligation]:
    out = []
    for d in debts:
        if not d.minimum_payment:
            continue
        due = d.payment_due_date
        if due is not None and due < today:
            continue  # an old statement: the next one hasn't arrived yet
        since = (due or today) - timedelta(days=STATEMENT_WINDOW_DAYS)
        paid = sum(
            (p.amount for p in payments if p.debt_id == d.id and p.on >= since), ZERO
        )
        out.append(Obligation(f"Mínimo {d.bank_name}", due, d.minimum_payment, paid=paid))
    return out


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
) -> PositionInputs:
    return PositionInputs(
        today=today,
        horizon_end=horizon_end,
        balance=balance,
        incomes=tuple(expected_incomes(income_sources, credits, today, horizon_end)),
        obligations=(
            *planned_obligations(planned_payments, today, horizon_end),
            *debt_obligations(debts, debt_payments, today),
        ),
        pay_due_on_payday=pay_due_on_payday,
    )
