"""Reconcile a bank-statement CSV against the transactions table.

The monthly statement is the authoritative record; per-transaction emails
sometimes get lost or arrive without a parseable template. This script
compares statement rows against what email sync already stored and inserts
only the missing ones (interest, missed notifications, etc.).

CSV columns: date (YYYY-MM-DD, local), description, amount, type (debit|credit).

Usage:
    docker compose run --rm backend python -m app.scripts.reconcile_statement \
        statements/2026-06-008-22715-9.csv --account 008-22715-9 --dry-run
    # then without --dry-run to commit

Matching: statement rows and DB rows are bucketed by (local date, amount,
type) and matched by count — the statement has no timestamps, so two
same-day same-amount rows are indistinguishable and matched as a group.
Unmatched statement rows get a second pass with ±1 day tolerance (email
timestamp vs statement posting date can differ across midnight) before
being declared missing.

Inserted rows are idempotent: raw_email_reference is
"statement:<account>:<date>:<row_index>", so a re-run finds them in the DB
and the deficit is zero.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from app.core.time_utils import user_tz
from app.db.session import AsyncSessionLocal
from app.models.provider_connection import ProviderConnection
from app.models.transaction import Transaction, TransactionType
from app.services.categorizer import categorize

log = logging.getLogger("reconcile_statement")

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


def _load_csv(path: Path) -> list[StatementRow]:
    rows: list[StatementRow] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for i, raw in enumerate(csv.DictReader(fh)):
            rows.append(
                StatementRow(
                    index=i,
                    local_date=date.fromisoformat(raw["date"].strip()),
                    description=raw["description"].strip(),
                    amount=Decimal(raw["amount"].strip()),
                    tx_type=TransactionType(raw["type"].strip()),
                )
            )
    return rows


def _bucket_key(local_date: date, amount: Decimal, tx_type: TransactionType) -> tuple:
    return (local_date, amount, tx_type)


def _category_for(description: str) -> str | None:
    for prefix, category in _CATEGORY_OVERRIDES:
        if description.upper().startswith(prefix.upper()):
            return category
    return categorize(description)


async def run(csv_path: Path, account: str, *, dry_run: bool) -> None:
    statement = _load_csv(csv_path)
    if not statement:
        log.info("empty statement, nothing to do")
        return

    tz = user_tz()
    period_start = min(r.local_date for r in statement)
    period_end = max(r.local_date for r in statement)
    # DB window padded by the ±1 day matching tolerance.
    window_start = datetime.combine(period_start - timedelta(days=1), time.min, tz)
    window_end = datetime.combine(period_end + timedelta(days=2), time.min, tz)

    async with AsyncSessionLocal() as db:
        connection = (
            await db.execute(select(ProviderConnection).limit(1))
        ).scalar_one_or_none()
        if connection is None:
            raise SystemExit("no provider_connection found — connect Gmail first")

        db_rows = (
            await db.execute(
                select(Transaction).where(
                    Transaction.user_id == connection.user_id,
                    Transaction.occurred_at >= window_start,
                    Transaction.occurred_at < window_end,
                )
            )
        ).scalars().all()

        # Bucket DB rows by (local date, amount, type); each DB row can absorb
        # one statement row.
        db_buckets: dict[tuple, int] = defaultdict(int)
        for t in db_rows:
            local_day = t.occurred_at.astimezone(tz).date()
            db_buckets[_bucket_key(local_day, t.amount, t.transaction_type)] += 1

        matched = 0
        missing: list[StatementRow] = []
        # Pass 1: exact date. Pass 2: ±1 day.
        pending = list(statement)
        for offsets in ((0,), (-1, 1)):
            still_pending: list[StatementRow] = []
            for row in pending:
                for off in offsets:
                    key = _bucket_key(
                        row.local_date + timedelta(days=off), row.amount, row.tx_type
                    )
                    if db_buckets[key] > 0:
                        db_buckets[key] -= 1
                        matched += 1
                        break
                else:
                    still_pending.append(row)
            pending = still_pending
        missing = pending

        log.info(
            "statement rows=%d matched=%d missing=%d",
            len(statement), matched, len(missing),
        )

        for row in missing:
            category = _category_for(row.description)
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

        if dry_run:
            log.info("dry-run: no changes committed")
        else:
            await db.commit()
            log.info("committed %d new transactions", len(missing))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path, help="Statement CSV path")
    parser.add_argument("--account", required=True, help="Account number for the dedupe reference")
    parser.add_argument("--dry-run", action="store_true", help="Print intended inserts, do not commit")
    args = parser.parse_args()
    asyncio.run(run(args.csv_path, args.account, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
