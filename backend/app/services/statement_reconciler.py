"""Shared statement-reconciliation logic used by the manual CSV script
(`app/scripts/reconcile_statement.py`) and the automatic email→PDF flow
(`app/services/statement_sync.py`).

The monthly statement is authoritative; per-transaction emails sometimes get
lost or don't match any parser template. This module cross-references
statement rows against what's already in the DB and inserts only what's
missing (interest, fees, missed notifications).

Matching: statement rows and DB rows are bucketed by (local date, amount,
type) and matched by count — the statement has no timestamps, so two
same-day same-amount rows are indistinguishable and matched as a group.
Unmatched statement rows get a second pass with ±1 day tolerance (email
timestamp vs statement posting date can differ across midnight) before being
declared missing.

Inserted rows are idempotent: raw_email_reference is
"statement:<account>:<date>:<row_index>", so re-running finds them in the DB
and the deficit is zero.
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import user_tz
from app.models.provider_connection import ProviderConnection
from app.models.transaction import Transaction, TransactionType
from app.services.categorizer import categorize

log = logging.getLogger(__name__)

# Statement rows that are internal movements, not spending. Debit Bre-B rows
# are intentionally NOT here: a Bre-B out can be paying a person (spending)
# or moving money to an own account — we can't tell from the statement, so
# they stay uncategorized for the user/matcher to resolve.
_CATEGORY_OVERRIDES: list[tuple[str, str]] = [
    ("RETIRO", "cash_withdrawal"),
    ("Pago tarjeta canal electronico", "transfer"),  # paying own credit card
]


@dataclass
class StatementRow:
    index: int
    local_date: date
    description: str
    amount: Decimal
    tx_type: TransactionType


@dataclass
class ReconcileResult:
    matched: int
    missing: list[StatementRow]
    inserted: int


def category_for(description: str) -> str | None:
    for prefix, category in _CATEGORY_OVERRIDES:
        if description.upper().startswith(prefix.upper()):
            return category
    return categorize(description)


def _bucket_key(local_date: date, amount: Decimal, tx_type: TransactionType) -> tuple:
    return (local_date, amount, tx_type)


def match_statement_rows(
    statement: list[StatementRow],
    db_rows: list[tuple[date, Decimal, TransactionType]],
) -> tuple[int, list[StatementRow]]:
    """Pure matching core — no DB access, fully unit-testable.

    ``db_rows`` is (local_date, amount, transaction_type) per existing DB
    transaction in the reconciliation window. Returns (matched_count,
    missing_rows).
    """
    db_buckets: dict[tuple, int] = defaultdict(int)
    for local_day, amount, tx_type in db_rows:
        db_buckets[_bucket_key(local_day, amount, tx_type)] += 1

    matched = 0
    pending = list(statement)
    # Pass 1: exact date. Pass 2: ±1 day.
    for offsets in ((0,), (-1, 1)):
        still_pending: list[StatementRow] = []
        for row in pending:
            for off in offsets:
                key = _bucket_key(row.local_date + timedelta(days=off), row.amount, row.tx_type)
                if db_buckets[key] > 0:
                    db_buckets[key] -= 1
                    matched += 1
                    break
            else:
                still_pending.append(row)
        pending = still_pending

    return matched, pending


async def reconcile_rows(
    db: AsyncSession,
    connection: ProviderConnection,
    account: str,
    rows: list[StatementRow],
    *,
    dry_run: bool,
) -> ReconcileResult:
    """Fetch DB rows for the statement's date window, match, and stage the
    missing ones for insert (unless ``dry_run``). Caller is responsible for
    ``db.commit()``. Thin DB wrapper around ``match_statement_rows``."""
    if not rows:
        return ReconcileResult(matched=0, missing=[], inserted=0)

    tz = user_tz()
    period_start = min(r.local_date for r in rows)
    period_end = max(r.local_date for r in rows)
    # Window padded by the ±1 day matching tolerance.
    window_start = datetime.combine(period_start - timedelta(days=1), time.min, tz)
    window_end = datetime.combine(period_end + timedelta(days=2), time.min, tz)

    db_transactions = (
        await db.execute(
            select(Transaction).where(
                Transaction.user_id == connection.user_id,
                Transaction.occurred_at >= window_start,
                Transaction.occurred_at < window_end,
            )
        )
    ).scalars().all()

    db_rows = [
        (t.occurred_at.astimezone(tz).date(), t.amount, t.transaction_type)
        for t in db_transactions
    ]

    matched, missing = match_statement_rows(rows, db_rows)

    log.info(
        "statement_reconcile account=%s rows=%d matched=%d missing=%d",
        account, len(rows), matched, len(missing),
    )

    inserted = 0
    for row in missing:
        category = category_for(row.description)
        reference = f"statement:{account}:{row.local_date.isoformat()}:{row.index}"
        log.info(
            "%s insert %s %s %s $%s category=%s ref=%s",
            "would" if dry_run else "will",
            row.local_date, row.tx_type.value, row.description,
            f"{row.amount:,.2f}", category, reference,
        )
        if dry_run:
            continue
        db.add(
            Transaction(
                id=uuid.uuid4(),
                user_id=connection.user_id,
                provider_connection_id=connection.id,
                amount=row.amount,
                merchant=row.description,
                category=category,
                transaction_type=row.tx_type,
                currency="COP",
                # Statement has no time of day; noon local keeps the row
                # inside the same local day after any UTC conversion.
                occurred_at=datetime.combine(row.local_date, time(12, 0), tz),
                raw_email_reference=reference,
            )
        )
        inserted += 1

    return ReconcileResult(matched=matched, missing=missing, inserted=inserted)
