"""Backfill `transactions.category` for rows that were synced before the
categorizer existed (or before a rule update).

Usage:
    docker compose run --rm backend python -m app.scripts.recategorize
    docker compose run --rm backend python -m app.scripts.recategorize --all
    docker compose run --rm backend python -m app.scripts.recategorize --dry-run

Default: only touches rows where `category IS NULL`. `--all` rewrites every
row (skipping the protected categories `transfer` and `cash_withdrawal`,
which are set by the matcher/parser and must not be clobbered).
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy import select, update

from app.db.session import AsyncSessionLocal
from app.models.transaction import Transaction
from app.services.categorizer import categorize

PROTECTED_CATEGORIES = ("transfer", "cash_withdrawal")

log = logging.getLogger("recategorize")


async def run(*, all_rows: bool, dry_run: bool) -> None:
    async with AsyncSessionLocal() as db:
        stmt = select(Transaction.id, Transaction.merchant, Transaction.category)
        if not all_rows:
            stmt = stmt.where(Transaction.category.is_(None))
        else:
            stmt = stmt.where(Transaction.category.notin_(PROTECTED_CATEGORIES) | Transaction.category.is_(None))

        rows = (await db.execute(stmt)).all()
        log.info("scanned %d candidate rows", len(rows))

        changed = 0
        for row in rows:
            new_category = categorize(row.merchant)
            if new_category == row.category:
                continue
            changed += 1
            if dry_run:
                log.info(
                    "would update id=%s merchant=%r %s -> %s",
                    row.id, row.merchant, row.category, new_category,
                )
                continue
            await db.execute(
                update(Transaction)
                .where(Transaction.id == row.id)
                .values(category=new_category)
            )

        if dry_run:
            log.info("dry-run: %d rows would change", changed)
        else:
            await db.commit()
            log.info("updated %d rows", changed)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="Re-run on all rows, not only NULL ones")
    parser.add_argument("--dry-run", action="store_true", help="Print intended changes, do not commit")
    args = parser.parse_args()
    asyncio.run(run(all_rows=args.all, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
