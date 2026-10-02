"""Pair outgoing Itaú/Davivienda transfers with incoming credits at destination banks.

Itaú's outgoing-transfer email carries no recipient — only "Canal: Portal
Internet" — and Davivienda's Bre-B key transfers don't name the destination
bank either. To avoid counting transfers to the user's own Nequi/Daviplata/
Falabella accounts as spending, we pair those debits with the "you received
$X" notifications from the destination banks: exact amount, ±10 minute
window. Paired rows get ``category="transfer"`` and share a
``transfer_pair_id``. Full design in PARSERS.md § "Pareo de transferencias".

Debits that stay unpaired keep their category (they were likely real
payments to third parties).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Protocol, Sequence

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction, TransactionType
from app.parsers.davivienda import LLAVE_MERCHANT

log = logging.getLogger(__name__)

PAIRING_WINDOW = timedelta(minutes=10)
LOOKBACK = timedelta(days=7)
# Card payment receipts arrive within seconds of the funding bank debit
# (PSE from Davivienda, "Pago exitoso" from Nequi); allow some slack.
DEBT_PAYMENT_WINDOW = timedelta(minutes=30)

# Debit merchants set by the source-bank parsers (Itaú, Davivienda).
SOURCE_MERCHANTS = ("Portal Internet", LLAVE_MERCHANT)
# Credit merchants set by the destination-bank parsers.
DESTINATION_MERCHANTS = ("Nequi", "Daviplata", "Banco Falabella")


class _Pairable(Protocol):
    id: uuid.UUID
    amount: object
    occurred_at: datetime


def pair_transfers(
    debits: Sequence[_Pairable],
    credits: Sequence[_Pairable],
    *,
    window: timedelta = PAIRING_WINDOW,
) -> list[tuple[uuid.UUID, uuid.UUID]]:
    """Greedy one-to-one pairing: exact amount, |Δt| within the window.

    Debits are processed oldest-first; each takes the *closest-in-time*
    unused credit of the same amount. Pure function — no DB access.
    """
    pairs: list[tuple[uuid.UUID, uuid.UUID]] = []
    used_credit_ids: set[uuid.UUID] = set()

    for debit in sorted(debits, key=lambda t: t.occurred_at):
        best = None
        best_delta = None
        for credit in credits:
            if credit.id in used_credit_ids or credit.amount != debit.amount:
                continue
            delta = abs(credit.occurred_at - debit.occurred_at)
            if delta > window:
                continue
            if best_delta is None or delta < best_delta:
                best = credit
                best_delta = delta
        if best is not None:
            used_credit_ids.add(best.id)
            pairs.append((debit.id, best.id))

    return pairs


async def match_transfers(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Pair recent unmatched candidates for a user. Returns pairs created."""
    since = datetime.now(timezone.utc) - LOOKBACK

    base = (
        select(Transaction.id, Transaction.amount, Transaction.occurred_at)
        .where(
            Transaction.user_id == user_id,
            Transaction.is_pairing_candidate.is_(True),
            Transaction.transfer_pair_id.is_(None),
            Transaction.occurred_at >= since,
        )
    )

    debit_rows = (
        await db.execute(
            base.where(
                Transaction.transaction_type == TransactionType.debit,
                Transaction.merchant.in_(SOURCE_MERCHANTS),
            )
        )
    ).all()
    credit_rows = (
        await db.execute(
            base.where(
                Transaction.transaction_type == TransactionType.credit,
                Transaction.merchant.in_(DESTINATION_MERCHANTS),
            )
        )
    ).all()

    pairs = pair_transfers(debit_rows, credit_rows)
    for debit_id, credit_id in pairs:
        pair_id = uuid.uuid4()
        await db.execute(
            update(Transaction)
            .where(Transaction.id.in_([debit_id, credit_id]))
            .values(category="transfer", transfer_pair_id=pair_id)
        )

    if pairs:
        await db.commit()
        log.info(
            "transfer_matcher paired",
            extra={"user_id": str(user_id), "pairs": len(pairs)},
        )
    return len(pairs)


async def match_debt_payments(
    db: AsyncSession, user_id: uuid.UUID, *, since: datetime | None = None
) -> int:
    """Pair credit-card payment receipts with the bank debit that funded them.

    The receipt (credit, category "debt_payment", linked to a debt) and the
    bank debit are the same money: the debit is re-tagged "debt_payment" so
    the card payment isn't counted as spending on top of the card purchases.
    Exact amount, ±30 min. Returns pairs created.
    """
    since = since or datetime.now(timezone.utc) - LOOKBACK

    unpaired = (
        Transaction.user_id == user_id,
        Transaction.transfer_pair_id.is_(None),
        Transaction.occurred_at >= since,
    )
    receipts = (
        await db.execute(
            select(Transaction.id, Transaction.amount, Transaction.occurred_at).where(
                *unpaired,
                Transaction.transaction_type == TransactionType.credit,
                Transaction.category == "debt_payment",
                Transaction.debt_id.is_not(None),
            )
        )
    ).all()
    if not receipts:
        return 0
    debits = (
        await db.execute(
            select(Transaction.id, Transaction.amount, Transaction.occurred_at).where(
                *unpaired,
                Transaction.transaction_type == TransactionType.debit,
                Transaction.debt_id.is_(None),
                or_(
                    Transaction.category.is_(None),
                    Transaction.category.notin_(("transfer", "debt_payment")),
                ),
            )
        )
    ).all()

    pairs = pair_transfers(debits, receipts, window=DEBT_PAYMENT_WINDOW)
    for debit_id, receipt_id in pairs:
        pair_id = uuid.uuid4()
        await db.execute(
            update(Transaction)
            .where(Transaction.id == debit_id)
            .values(category="debt_payment", transfer_pair_id=pair_id)
        )
        await db.execute(
            update(Transaction)
            .where(Transaction.id == receipt_id)
            .values(transfer_pair_id=pair_id)
        )

    if pairs:
        await db.commit()
        log.info(
            "debt_payment_matcher paired",
            extra={"user_id": str(user_id), "pairs": len(pairs)},
        )
    return len(pairs)
