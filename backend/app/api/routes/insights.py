"""Insights: unusual spending alerts + financial health score.

Both computed on the fly (no persisted state) from pure services:
`spending_anomalies.py` and `health_score.py`.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.core.time_utils import (
    current_month_local,
    month_bounds,
    not_in_excluded,
    user_tz,
)
from app.models.budget import Budget
from app.models.debt import Debt
from app.models.income_source import IncomeSource
from app.models.savings_goal import SavingsGoal
from app.models.transaction import Transaction, TransactionType
from app.services.budget_status import budget_alert_status
from app.services.health_score import compute_health_score
from app.services.spending_anomalies import SpendingAnomaly, detect_anomalies

router = APIRouter(prefix="/insights", tags=["insights"])

_EXCLUDED = ("transfer", "cash_withdrawal")
HISTORY_MONTHS = 6


class AnomalyOut(BaseModel):
    category: str
    current: Decimal
    historical_avg: Decimal
    ratio: Decimal


class UnusualSpendingResponse(BaseModel):
    month: str
    items: list[AnomalyOut]


class HealthScoreResponse(BaseModel):
    total: int
    debt: int
    budgets: int
    savings: int
    anomalies: int


def _shift_month(month: str, delta: int) -> str:
    year, m = (int(p) for p in month.split("-"))
    idx = year * 12 + (m - 1) + delta
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


async def _detect_user_anomalies(
    user_id, db: DbSession
) -> tuple[str, list[SpendingAnomaly]]:
    month = current_month_local()
    current_start, current_end = month_bounds(month)
    history_start, _ = month_bounds(_shift_month(month, -HISTORY_MONTHS))

    current_rows = await db.execute(
        select(
            Transaction.category,
            func.coalesce(func.sum(Transaction.amount), 0).label("total"),
        )
        .where(
            Transaction.user_id == user_id,
            Transaction.transaction_type == TransactionType.debit,
            Transaction.occurred_at >= current_start,
            Transaction.occurred_at < current_end,
            Transaction.category.is_not(None),
            not_in_excluded(Transaction.category, _EXCLUDED),
        )
        .group_by(Transaction.category)
    )
    current_by_category = {row.category: Decimal(row.total) for row in current_rows.all()}

    # One total per (category, month) in the lookback window, current excluded.
    month_key = func.to_char(
        func.timezone(str(user_tz()), Transaction.occurred_at), "YYYY-MM"
    )
    history_rows = await db.execute(
        select(
            Transaction.category,
            month_key.label("month"),
            func.coalesce(func.sum(Transaction.amount), 0).label("total"),
        )
        .where(
            Transaction.user_id == user_id,
            Transaction.transaction_type == TransactionType.debit,
            Transaction.occurred_at >= history_start,
            Transaction.occurred_at < current_start,
            Transaction.category.is_not(None),
            not_in_excluded(Transaction.category, _EXCLUDED),
        )
        .group_by(Transaction.category, month_key)
    )
    history_by_category: dict[str, list[Decimal]] = {}
    for row in history_rows.all():
        history_by_category.setdefault(row.category, []).append(Decimal(row.total))

    return month, detect_anomalies(current_by_category, history_by_category)


@router.get("/unusual-spending", response_model=UnusualSpendingResponse)
async def unusual_spending(
    current_user: CurrentUser, db: DbSession
) -> UnusualSpendingResponse:
    month, anomalies = await _detect_user_anomalies(current_user.id, db)
    return UnusualSpendingResponse(
        month=month,
        items=[
            AnomalyOut(
                category=a.category,
                current=a.current,
                historical_avg=a.historical_avg,
                ratio=a.ratio,
            )
            for a in anomalies
        ],
    )


@router.get("/health-score", response_model=HealthScoreResponse)
async def health_score(
    current_user: CurrentUser, db: DbSession
) -> HealthScoreResponse:
    # Debts
    debts_result = await db.execute(
        select(Debt).where(Debt.user_id == current_user.id)
    )
    debts = debts_result.scalars().all()
    total_min = sum((d.minimum_payment or Decimal("0") for d in debts), Decimal("0"))

    # Monthly income from the configured calendar (None when not set up).
    income_result = await db.execute(
        select(func.coalesce(func.sum(IncomeSource.amount), 0)).where(
            IncomeSource.user_id == current_user.id
        )
    )
    monthly_income = Decimal(income_result.scalar_one())
    income_or_none = monthly_income if monthly_income > 0 else None

    # Budget adherence this month.
    month = current_month_local()
    start, end = month_bounds(month)
    budgets_result = await db.execute(
        select(Budget).where(Budget.user_id == current_user.id)
    )
    budgets = budgets_result.scalars().all()
    warning = exceeded = 0
    if budgets:
        spent_rows = await db.execute(
            select(
                Transaction.category,
                func.coalesce(func.sum(Transaction.amount), 0).label("total"),
            )
            .where(
                Transaction.user_id == current_user.id,
                Transaction.transaction_type == TransactionType.debit,
                Transaction.occurred_at >= start,
                Transaction.occurred_at < end,
            )
            .group_by(Transaction.category)
        )
        spent_by_category = {row.category: Decimal(row.total) for row in spent_rows.all()}
        for b in budgets:
            status_ = budget_alert_status(
                spent_by_category.get(b.category, Decimal("0")), b.monthly_limit
            )
            if status_ == "warning":
                warning += 1
            elif status_ == "exceeded":
                exceeded += 1

    # Savings goals progress.
    goals_result = await db.execute(
        select(SavingsGoal).where(SavingsGoal.user_id == current_user.id)
    )
    goal_pcts = [
        min(100, int(g.current_amount * 100 / g.target_amount))
        for g in goals_result.scalars().all()
        if g.target_amount > 0
    ]

    _, anomalies = await _detect_user_anomalies(current_user.id, db)

    breakdown = compute_health_score(
        has_debts=len(debts) > 0,
        total_minimum_payments=total_min,
        monthly_income=income_or_none,
        budget_count=len(budgets),
        budget_warning_count=warning,
        budget_exceeded_count=exceeded,
        goal_pcts=goal_pcts,
        anomaly_count=len(anomalies),
    )
    return HealthScoreResponse(
        total=breakdown.total,
        debt=breakdown.debt,
        budgets=breakdown.budgets,
        savings=breakdown.savings,
        anomalies=breakdown.anomalies,
    )
