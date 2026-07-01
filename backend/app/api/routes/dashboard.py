# app/api/routes/dashboard.py
"""GET /dashboard — consolidated view: 6-month trend, current month, debts.

Three queries run concurrently. Month windowing uses settings.user_timezone
(default America/Bogota) — same rule as GET /transactions/summary.
Spending excludes transfer and cash_withdrawal categories.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.core.time_utils import current_month_local, month_bounds, not_in_excluded
from app.models.debt import Debt
from app.models.transaction import Transaction, TransactionType
from app.schemas.dashboard import (
    CurrentMonthSnapshot,
    DashboardResponse,
    DebtSnapshot,
    MonthCategoryItem,
    MonthTrendEntry,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_EXCLUDED = ("transfer", "cash_withdrawal")


@router.get("", response_model=DashboardResponse)
async def get_dashboard(current_user: CurrentUser, db: DbSession) -> DashboardResponse:
    current_month = current_month_local()
    trend_months = _six_months(current_month)
    trend_start, _ = month_bounds(trend_months[0])

    trend_rows, tx_count, debt_row = await asyncio.gather(
        _fetch_trend(db, current_user.id, trend_start),
        _fetch_count(db, current_user.id, current_month),
        _fetch_debts(db, current_user.id),
    )

    monthly_trend = _build_trend(trend_rows, trend_months)
    last = monthly_trend[-1]

    return DashboardResponse(
        monthly_trend=monthly_trend,
        current_month=CurrentMonthSnapshot(
            month=last.month,
            total_spent=last.total_spent,
            by_category=last.by_category,
            transaction_count=tx_count,
        ),
        debts=DebtSnapshot(
            total_debt=Decimal(str(debt_row.total_debt)),
            total_minimum_payment=Decimal(str(debt_row.total_min)),
            debt_count=debt_row.debt_count,
        ),
    )


async def _fetch_trend(db: AsyncSession, user_id: UUID, trend_start: datetime) -> list:
    tz_str = settings.user_timezone
    local_ts = func.timezone(tz_str, func.timezone("UTC", Transaction.occurred_at))
    month_col = func.date_trunc("month", local_ts).label("month")

    result = await db.execute(
        select(
            month_col,
            Transaction.category,
            func.sum(Transaction.amount).label("total"),
            func.count().label("cnt"),
        )
        .where(
            Transaction.user_id == user_id,
            Transaction.transaction_type == TransactionType.debit,
            not_in_excluded(Transaction.category, _EXCLUDED),
            Transaction.occurred_at >= trend_start,
        )
        .group_by(month_col, Transaction.category)
        .order_by(month_col)
    )
    return result.all()


async def _fetch_count(db: AsyncSession, user_id: UUID, current_month: str) -> int:
    month_start, month_end = month_bounds(current_month)
    result = await db.execute(
        select(func.count()).where(
            Transaction.user_id == user_id,
            Transaction.occurred_at >= month_start,
            Transaction.occurred_at < month_end,
        )
    )
    return result.scalar_one()


async def _fetch_debts(db: AsyncSession, user_id: UUID):
    result = await db.execute(
        select(
            func.count().label("debt_count"),
            func.coalesce(func.sum(Debt.total_amount), 0).label("total_debt"),
            func.coalesce(func.sum(Debt.minimum_payment), 0).label("total_min"),
        ).where(Debt.user_id == user_id)
    )
    return result.one()


def _six_months(current: str) -> list[str]:
    """Returns 6 YYYY-MM strings: [5-months-ago, ..., current], oldest first."""
    y, m = int(current[:4]), int(current[5:])
    result = []
    for i in range(5, -1, -1):
        mi = m - i
        yi = y
        while mi <= 0:
            mi += 12
            yi -= 1
        result.append(f"{yi:04d}-{mi:02d}")
    return result


def _build_trend(rows, months: list[str]) -> list[MonthTrendEntry]:
    raw: dict[str, list[MonthCategoryItem]] = defaultdict(list)
    for row in rows:
        month_dt: datetime = row.month
        month_str = f"{month_dt.year:04d}-{month_dt.month:02d}"
        raw[month_str].append(
            MonthCategoryItem(
                category=row.category,
                total=Decimal(str(row.total)),
                count=row.cnt,
            )
        )

    trend = []
    for month_str in months:
        items = raw.get(month_str, [])
        trend.append(
            MonthTrendEntry(
                month=month_str,
                total_spent=sum((item.total for item in items), Decimal("0")),
                by_category=items,
            )
        )
    return trend
