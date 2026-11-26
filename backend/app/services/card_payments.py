"""Live minimum payment of email-linked card debts, read from the debt, its
latest saved statement and the card movements since the cut-off. Shared by
GET /debts and the dashboard's debt KPI."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import user_tz
from app.models.card_statement import SavedStatement
from app.models.debt import Debt
from app.models.transaction import Transaction
from app.services.card_statement import card_movement_clause, is_card_payment
from app.services.cards import CurrentPayment, current_card_payment


def effective_minimum(debt: Debt, current: dict[uuid.UUID, CurrentPayment]) -> Decimal:
    """The live minimum for a linked card, the stored one for the rest."""
    payment = current.get(debt.id)
    if payment is not None:
        return payment.amount
    return debt.minimum_payment or Decimal("0")


async def current_card_payments(
    db: AsyncSession, user_id: uuid.UUID, debts: Sequence[Debt]
) -> dict[uuid.UUID, CurrentPayment]:
    """Current minimum and due date of the email-linked cards with a
    statement; due dates come from the saved statements when there are."""
    cards = [d for d in debts if d.email_format is not None and d.statement_at is not None]
    if not cards:
        return {}
    ids = [d.id for d in cards]
    latest: dict[uuid.UUID, SavedStatement] = {}
    for st in (
        await db.execute(
            select(SavedStatement)
            .where(SavedStatement.debt_id.in_(ids))
            .order_by(SavedStatement.period_end.desc())
        )
    ).scalars():
        latest.setdefault(st.debt_id, st)
    movements = (
        await db.execute(
            select(
                Transaction.debt_id,
                Transaction.occurred_at,
                Transaction.amount,
                Transaction.transaction_type,
                Transaction.category,
            ).where(
                Transaction.user_id == user_id,
                Transaction.debt_id.in_(ids),
                card_movement_clause(cards),
                Transaction.occurred_at >= min(d.statement_at for d in cards),
            )
        )
    ).all()
    tz = user_tz()
    out: dict[uuid.UUID, CurrentPayment] = {}
    for d in cards:
        st = latest.get(d.id)
        since = [m for m in movements if m.debt_id == d.id and m.occurred_at >= d.statement_at]
        # A statement newer than the saved PDF (email only) wins.
        use_saved = st is not None and st.due_date is not None and (
            d.payment_due_date is None or st.due_date >= d.payment_due_date
        )
        payment = current_card_payment(
            statement_minimum=st.minimum_payment if use_saved else d.minimum_payment,
            statement_due=st.due_date if use_saved else d.payment_due_date,
            cutoff=st.period_end if use_saved else None,
            paid_since_cutoff=sum(
                (m.amount for m in since if is_card_payment(m.transaction_type, m.category)),
                Decimal("0"),
            ),
            purchases_since_cutoff=[
                (m.occurred_at.astimezone(tz).date(), m.amount)
                for m in since
                if not is_card_payment(m.transaction_type, m.category)
            ],
            next_installments=d.next_installments,
            balance=d.total_amount,
        )
        if payment is not None:
            out[d.id] = payment
    return out
