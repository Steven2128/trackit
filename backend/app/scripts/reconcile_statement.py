"""Reconcile a bank-statement CSV against the transactions table.

The monthly statement is the authoritative record; per-transaction emails
sometimes get lost or arrive without a parseable template. This script loads
statement rows from a CSV and delegates matching/insertion to
`app/services/statement_reconciler.py` — the same core used by the automatic
email→PDF flow in `app/services/statement_sync.py`.

CSV columns: date (YYYY-MM-DD, local), description, amount, type (debit|credit).

Usage:
    docker compose run --rm backend python -m app.scripts.reconcile_statement \
        statements/2026-06-008-22715-9.csv --account 008-22715-9 --dry-run
    # then without --dry-run to commit
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import logging
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.provider_connection import ProviderConnection
from app.models.transaction import TransactionType
from app.services.statement_reconciler import StatementRow, reconcile_rows

log = logging.getLogger("reconcile_statement")


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


async def run(csv_path: Path, account: str, *, dry_run: bool) -> None:
    statement = _load_csv(csv_path)
    if not statement:
        log.info("empty statement, nothing to do")
        return

    async with AsyncSessionLocal() as db:
        connection = (
            await db.execute(select(ProviderConnection).limit(1))
        ).scalar_one_or_none()
        if connection is None:
            raise SystemExit("no provider_connection found — connect Gmail first")

        result = await reconcile_rows(db, connection, account, statement, dry_run=dry_run)

        if dry_run:
            log.info("dry-run: no changes committed")
        else:
            await db.commit()
            log.info("committed %d new transactions", result.inserted)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path, help="Statement CSV path")
    parser.add_argument(
        "--account", required=True, help="Account number for the dedupe reference"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print intended inserts, do not commit"
    )
    args = parser.parse_args()
    asyncio.run(run(args.csv_path, args.account, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
