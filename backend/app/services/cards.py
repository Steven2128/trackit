"""The credit-cards view: pure pieces over saved statements (the route in
app/api/routes/cards.py loads the rows)."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol, Sequence

ZERO = Decimal("0")


class LineLike(Protocol):
    posted_on: date
    description: str
    amount: Decimal
    billed: Decimal | None
    installment: int | None
    installments: int | None
    pending: Decimal | None


@dataclass(frozen=True)
class InstallmentPlan:
    description: str
    purchased_on: date
    amount: Decimal
    installment: int
    installments: int
    billed: Decimal | None
    pending: Decimal
    next_amount: Decimal
    remaining: int


def add_month(d: date) -> date:
    y, m = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def installment_plans(lines: Sequence[LineLike]) -> list[InstallmentPlan]:
    """Purchases of the last statement that were split in more than one
    installment — the ones still running first, largest debt on top."""
    plans = []
    for line in lines:
        if not line.installments or line.installments < 2 or not line.installment:
            continue
        remaining = max(line.installments - line.installment, 0)
        pending = line.pending or ZERO
        next_amount = (pending / remaining).quantize(Decimal("0.01")) if remaining else ZERO
        plans.append(
            InstallmentPlan(
                description=line.description,
                purchased_on=line.posted_on,
                amount=line.amount,
                installment=line.installment,
                installments=line.installments,
                billed=line.billed,
                pending=pending,
                next_amount=next_amount,
                remaining=remaining,
            )
        )
    return sorted(plans, key=lambda p: (p.remaining == 0, -p.pending))


def statement_totals(lines: Sequence[LineLike], period_start: date | None) -> tuple[Decimal, Decimal]:
    """(bought in the period, paid in the period)."""
    purchases = sum(
        (
            line.amount
            for line in lines
            if line.amount > 0 and (period_start is None or line.posted_on >= period_start)
        ),
        ZERO,
    )
    payments = sum((-line.amount for line in lines if line.amount < 0), ZERO)
    return purchases, payments


@dataclass(frozen=True)
class CurrentPayment:
    """What the card asks for right now and by when."""

    amount: Decimal
    due_date: date
    # True once the last statement is covered: the amount is the next
    # statement building up (installments + purchases), not a billed one.
    accruing: bool


def current_card_payment(
    *,
    statement_minimum: Decimal | None,
    statement_due: date | None,
    cutoff: date | None,
    paid_since_cutoff: Decimal,
    purchases_since_cutoff: Sequence[tuple[date, Decimal]],
    next_installments: Decimal | None,
    balance: Decimal,
) -> CurrentPayment | None:
    """The minimum to show on a card debt.

    While the last statement's minimum isn't covered, it's what's left of it
    by that statement's due date. Once it is, the next statement accrues: the
    installments it already carries plus every purchase up to the next
    cut-off (single-installment, billed whole), due a month after the last
    due date — the card keeps the same payment day every month. Never more
    than the balance."""
    if statement_due is None:
        return None
    pending = max((statement_minimum or ZERO) - paid_since_cutoff, ZERO)
    if pending > 0:
        return CurrentPayment(pending, statement_due, accruing=False)
    next_cutoff = add_month(cutoff) if cutoff is not None else None
    bought = sum(
        (amount for day, amount in purchases_since_cutoff
         if next_cutoff is None or day <= next_cutoff),
        ZERO,
    )
    amount = min(bought + (next_installments or ZERO), max(balance, ZERO))
    return CurrentPayment(amount, add_month(statement_due), accruing=True)
