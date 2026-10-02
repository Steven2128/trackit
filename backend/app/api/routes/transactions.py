"""Read endpoints for transactions.

Month windowing respects ``settings.user_timezone`` (default America/Bogota)
because the user reasons about months in local time. Transactions are stored
in UTC, so we convert the local-month boundaries to UTC at query time.

Spending totals exclude internal movements (transfers between the user's own
accounts and cash withdrawals) per PARSERS.md — those still appear in the
raw list, just don't inflate ``total_spent`` / ``total_received``.
"""

from __future__ import annotations

import re
import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
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
    TransactionUpdate,
)
from app.services.categorizer import RULES

router = APIRouter(prefix="/transactions", tags=["transactions"])

EXCLUDED_FROM_SPENT_CATEGORIES = ("transfer", "cash_withdrawal", "debt_payment")
EXCLUDED_FROM_RECEIVED_CATEGORIES = ("transfer", "debt_payment")

# Manual recategorization accepts anything the system itself can emit:
# categorizer rules plus the layers reserved to transfer_matcher/parsers.
ALLOWED_CATEGORIES = {rule.category for rule in RULES} | set(
    EXCLUDED_FROM_SPENT_CATEGORIES
)

# User-defined categories are free-form slugs (mobile slugifies the display
# name). No registry table — a custom category exists while a budget or a
# transaction references it; budgets/status and dashboards group by string.
CUSTOM_CATEGORY_RE = re.compile(r"^[a-z0-9_]{1,64}$")


@router.get("", response_model=TransactionListResponse)
async def list_transactions(
    current_user: CurrentUser,
    db: DbSession,
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    category: str | None = Query(default=None),
    type: TransactionType | None = Query(default=None),
    debt_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> TransactionListResponse:
    filters = [Transaction.user_id == current_user.id]
    filters.extend(month_filter(month))
    if category is not None:
        filters.append(Transaction.category == category)
    if type is not None:
        filters.append(Transaction.transaction_type == type)
    if debt_id is not None:
        filters.append(Transaction.debt_id == debt_id)

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


@router.patch("/{transaction_id}", response_model=TransactionOut)
async def update_transaction(
    transaction_id: uuid.UUID,
    payload: TransactionUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> TransactionOut:
    """Manual edit (category and/or merchant name) — feeds budget bars,
    summaries and dashboard. Partial: only fields present in the body change."""
    provided = payload.model_fields_set
    if not provided:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="empty_update"
        )

    if "category" in provided and payload.category is not None:
        if (
            payload.category not in ALLOWED_CATEGORIES
            and not CUSTOM_CATEGORY_RE.match(payload.category)
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="unknown_category",
            )

    merchant: str | None = None
    if "merchant" in provided and payload.merchant is not None:
        merchant = payload.merchant.strip()
        if not merchant or len(merchant) > 255:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="invalid_merchant",
            )

    note: str | None = None
    if "note" in provided and payload.note is not None:
        note = payload.note.strip() or None
        if note is not None and len(note) > 500:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="invalid_note",
            )

    result = await db.execute(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == current_user.id,
        )
    )
    tx = result.scalar_one_or_none()
    if tx is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="transaction_not_found"
        )

    if "category" in provided:
        tx.category = payload.category
    if "merchant" in provided:
        tx.merchant = merchant
    if "note" in provided:
        tx.note = note
    await db.commit()
    await db.refresh(tx)
    return TransactionOut.model_validate(tx)


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
