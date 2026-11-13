"""Apply a credit-card statement PDF to its debt: the statement is the
authority, the per-purchase emails are only the running estimate.

- cut-off: purchases after it belong to the next statement
  (``debts.statement_at`` = the first instant after the cut-off day);
- installments of older purchases that the next statement will bill
  (``debts.next_installments``);
- purchases the emails missed (or made before the card was linked) are
  added as card movements;
- balance: the statement's total plus what was bought and minus what was
  paid after the cut-off;
- the statement itself, with every movement, is saved (card_statements)
  for the cards view.
"""

from __future__ import annotations

import logging
from datetime import datetime, time, timedelta
from decimal import Decimal
from typing import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import user_tz
from app.models.card_statement import SavedStatement, SavedStatementLine
from app.models.debt import Debt
from app.models.provider_connection import ProviderConnection
from app.models.transaction import Transaction, TransactionType
from app.parsers.cards.rappicard_statement import CardStatement
from app.services.categorizer import UserRule, categorize
from app.services.statement_reconciler import StatementRow, match_statement_rows

log = logging.getLogger(__name__)

# The statement dates a purchase when it posts, up to a few days after the
# purchase email (a Saturday-night Oxxo shows up on Monday).
POSTING_TOLERANCE_DAYS = 3


def cutoff_instant(statement: CardStatement) -> datetime:
    """The first instant of the day after the cut-off day, local time."""
    return datetime.combine(statement.period_end + timedelta(days=1), time.min, user_tz())


def balance_after(
    total_payment: Decimal,
    later: Sequence[tuple[TransactionType, Decimal]],
) -> Decimal:
    """Statement total + purchases − payments made after the cut-off."""
    balance = total_payment
    for tx_type, amount in later:
        balance += amount if tx_type is TransactionType.debit else -amount
    return max(balance, Decimal("0"))


async def save_statement(db: AsyncSession, debt: Debt, statement: CardStatement) -> SavedStatement:
    """Store the statement and its movements; reading the same statement
    again replaces what was stored. Caller commits."""
    saved = (
        await db.execute(
            select(SavedStatement).where(
                SavedStatement.debt_id == debt.id,
                SavedStatement.period_end == statement.period_end,
            )
        )
    ).scalar_one_or_none()
    if saved is None:
        saved = SavedStatement(user_id=debt.user_id, debt_id=debt.id, period_end=statement.period_end)
        db.add(saved)
    else:
        await db.execute(
            delete(SavedStatementLine).where(SavedStatementLine.statement_id == saved.id)
        )
    saved.period_start = statement.period_start
    saved.due_date = statement.due_date
    saved.minimum_payment = statement.minimum_payment
    saved.total_payment = statement.total_payment
    saved.credit_limit = statement.credit_limit
    await db.flush()
    for line in statement.lines:
        db.add(
            SavedStatementLine(
                statement_id=saved.id,
                position=line.index,
                posted_on=line.on,
                description=line.description[:255],
                amount=line.amount,
                billed=line.billed,
                installment=line.installment,
                installments=line.installments,
                pending=line.pending,
            )
        )
    return saved


async def apply_card_statement(
    db: AsyncSession,
    connection: ProviderConnection,
    debt: Debt,
    statement: CardStatement,
    user_rules: Sequence[UserRule] = (),
) -> int:
    """Returns how many missing purchases were added. Caller commits."""
    tz = user_tz()
    cutoff = cutoff_instant(statement)
    debt.statement_at = cutoff
    debt.next_installments = statement.next_installments or None
    await save_statement(db, debt, statement)

    purchases = statement.purchases
    inserted = 0
    if purchases:
        first = min(line.on for line in purchases)
        window_start = datetime.combine(first - timedelta(days=POSTING_TOLERANCE_DAYS), time.min, tz)
        existing = (
            await db.execute(
                select(Transaction.occurred_at, Transaction.amount, Transaction.transaction_type)
                .where(
                    Transaction.user_id == debt.user_id,
                    Transaction.debt_id == debt.id,
                    Transaction.occurred_at >= window_start,
                    Transaction.occurred_at < cutoff + timedelta(days=1),
                )
            )
        ).all()
        rows = [
            StatementRow(line.index, line.on, line.description, line.amount, TransactionType.debit)
            for line in purchases
        ]
        _, missing = match_statement_rows(
            rows,
            [(r.occurred_at.astimezone(tz).date(), r.amount, r.transaction_type) for r in existing],
            tolerance_days=POSTING_TOLERANCE_DAYS,
        )
        for row in missing:
            db.add(
                Transaction(
                    user_id=debt.user_id,
                    provider_connection_id=connection.id,
                    amount=row.amount,
                    merchant=row.description,
                    category=categorize(row.description, user_rules),
                    transaction_type=TransactionType.debit,
                    currency="COP",
                    # No time of day in the statement: noon keeps the local day.
                    occurred_at=datetime.combine(row.local_date, time(12, 0), tz),
                    raw_email_reference=(
                        f"statement:{debt.email_format}:{statement.period_end.isoformat()}:{row.index}"
                    ),
                    debt_id=debt.id,
                    source="card",
                    note="Leído del extracto (no llegó el correo de la compra)",
                )
            )
            inserted += 1

    if statement.total_payment is not None:
        later = (
            await db.execute(
                select(Transaction.transaction_type, Transaction.amount).where(
                    Transaction.user_id == debt.user_id,
                    Transaction.debt_id == debt.id,
                    Transaction.source == "card",
                    Transaction.occurred_at >= cutoff,
                )
            )
        ).all()
        debt.total_amount = balance_after(
            statement.total_payment, [(r.transaction_type, r.amount) for r in later]
        )

    log.info(
        "card_statement debt=%s cutoff=%s next_installments=%s inserted=%d",
        debt.id, statement.period_end, debt.next_installments, inserted,
    )
    return inserted
