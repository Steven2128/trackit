"""Someone else's part of a bill, handed over before it's due.

The brother transfers his part of the rent around the 5th; the rent is paid
later, in cash. A planned payment with ``partner_amount`` says how much to
expect. When a bank deposit of exactly that amount shows up, it stops being
income (category "reimbursement") and becomes a fund hold linked to the
payment: kept apart, shown with the payment in the fortnight, and used up
when the payment is paid (routes/plan.py).

One hold per payment at a time: a deposit that arrives while the previous
one is still held waits, uncategorized, until that one is used.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fund_hold import FundHold
from app.models.planned_payment import PlannedPayment
from app.models.transaction import Transaction, TransactionType

REIMBURSEMENT = "reimbursement"
# Deposits older than this are history, not this cycle's part.
LOOKBACK = timedelta(days=45)
_BANK_SOURCES = ("davivienda", "nequi")


def hold_name(payment_name: str) -> str:
    return f"{payment_name} · parte de otra persona"


async def hold_partner_money(
    db: AsyncSession, user_id: uuid.UUID, now: datetime | None = None
) -> int:
    """Turn matching deposits into holds. Returns how many were created."""
    now = now or datetime.now(timezone.utc)
    payments = (
        (
            await db.execute(
                select(PlannedPayment).where(
                    PlannedPayment.user_id == user_id,
                    PlannedPayment.partner_amount.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )
    created = 0
    for p in payments:
        held = (
            await db.execute(
                select(FundHold.id).where(
                    FundHold.user_id == user_id, FundHold.planned_payment_id == p.id
                )
            )
        ).first()
        if held is not None:
            continue
        deposit = (
            (
                await db.execute(
                    select(Transaction)
                    .where(
                        Transaction.user_id == user_id,
                        Transaction.transaction_type == TransactionType.credit,
                        Transaction.amount == p.partner_amount,
                        Transaction.category.is_(None),
                        Transaction.transfer_pair_id.is_(None),
                        Transaction.source.in_(_BANK_SOURCES),
                        Transaction.occurred_at >= now - LOOKBACK,
                    )
                    .order_by(Transaction.occurred_at)
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )
        if deposit is None:
            continue
        deposit.category = REIMBURSEMENT
        if not deposit.note:
            deposit.note = f"Parte de otra persona para {p.name}: guardada hasta pagarlo."
        db.add(
            FundHold(
                user_id=user_id,
                name=hold_name(p.name),
                amount=p.partner_amount,
                planned_payment_id=p.id,
            )
        )
        created += 1
    if created:
        await db.commit()
    return created
