"""Read endpoints for transactions.

Month windowing respects ``settings.user_timezone`` (default America/Bogota)
because the user reasons about months in local time. Transactions are stored
in UTC, so we convert the local-month boundaries to UTC at query time.

Spending totals exclude internal movements (transfers between the user's own
accounts and cash withdrawals) per PARSERS.md — those still appear in the
raw list, just don't inflate ``total_spent`` / ``total_received``.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Query
from sqlalchemy import func, select
from sqlalchemy.sql import ColumnElement

from app.api.deps import CurrentUser, DbSession
from app.core.time_utils import current_month_local, month_filter, not_in_excluded
from app.models.transaction import Transaction, TransactionType
from app.schemas.transaction import (
    CategorySummaryItem,
    TransactionListResponse,
    TransactionOut,
    TransactionSummary,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])

EXCLUDED_FROM_SPENT_CATEGORIES = ("transfer", "cash_withdrawal")
EXCLUDED_FROM_RECEIVED_CATEGORIES = ("transfer",)


@router.get("", response_model=TransactionListResponse)
async def list_transactions(
    current_user: CurrentUser,
    db: DbSession,
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    category: str | None = Query(default=None),
    type: TransactionType | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> TransactionListResponse:
    filters = [Transaction.user_id == current_user.id]
    filters.extend(month_filter(month))
    if category is not None:
        filters.append(Transaction.category == category)
    if type is not None:
        filters.append(Transaction.transaction_type == type)

    total_result = await db.execute(
        select(func.count()).select_from(Transaction).where(*filters)
    )
    total = total_result.scalar_one()

    rows_result = await db.execute(
        select(Transaction)
        .where(*filters)
        .order_by(Transaction.occurred_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = [TransactionOut.model_validate(t) for t in rows_result.scalars().all()]

    return TransactionListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/summary", response_model=TransactionSummary)
async def transactions_summary(
    current_user: CurrentUser,
    db: DbSession,
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
) -> TransactionSummary:
    resolved_month = month or current_month_local()
    month_clauses = month_filter(resolved_month)
    base_filter = [Transaction.user_id == current_user.id, *month_clauses]

    total_spent = await _sum_amount(
        db,
        [
            *base_filter,
            Transaction.transaction_type == TransactionType.debit,
            not_in_excluded(Transaction.category, EXCLUDED_FROM_SPENT_CATEGORIES),
        ],
    )
    total_received = await _sum_amount(
        db,
        [
            *base_filter,
            Transaction.transaction_type == TransactionType.credit,
            not_in_excluded(Transaction.category, EXCLUDED_FROM_RECEIVED_CATEGORIES),
        ],
    )

    by_category_rows = await db.execute(
        select(
            Transaction.category,
            func.coalesce(func.sum(Transaction.amount), 0).label("total"),
            func.count().label("count"),
        )
        .where(
            *base_filter,
            Transaction.transaction_type == TransactionType.debit,
            not_in_excluded(Transaction.category, EXCLUDED_FROM_SPENT_CATEGORIES),
        )
        .group_by(Transaction.category)
        .order_by(func.sum(Transaction.amount).desc())
    )
    by_category = [
        CategorySummaryItem(category=row.category, total=row.total, count=row.count)
        for row in by_category_rows.all()
    ]

    count_result = await db.execute(
        select(func.count()).select_from(Transaction).where(*base_filter)
    )
    transaction_count = count_result.scalar_one()

    return TransactionSummary(
        month=resolved_month,
        total_spent=total_spent,
        total_received=total_received,
        by_category=by_category,
        transaction_count=transaction_count,
    )


async def _sum_amount(db, filters: list[ColumnElement]) -> Decimal:
    result = await db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(*filters)
    )
    value = result.scalar_one()
    return Decimal(value) if not isinstance(value, Decimal) else value
