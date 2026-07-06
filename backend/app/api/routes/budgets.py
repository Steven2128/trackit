"""Budget CRUD + monthly status with 80%/100% alert levels.

`PUT /budgets/{category}` upserts — one budget per (user, category), the
limit applies to every month until changed. `GET /budgets/status` joins each
budget with the month's debit total for that category (same local-month
windowing as /transactions/summary).
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.core.time_utils import current_month_local, month_filter
from app.models.budget import Budget
from app.models.transaction import Transaction, TransactionType
from app.schemas.budget import (
    BudgetOut,
    BudgetStatusItem,
    BudgetStatusResponse,
    BudgetUpsert,
)
from app.services.budget_status import budget_alert_status, budget_pct

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get("", response_model=list[BudgetOut])
async def list_budgets(current_user: CurrentUser, db: DbSession) -> list[BudgetOut]:
    result = await db.execute(
        select(Budget).where(Budget.user_id == current_user.id).order_by(Budget.category)
    )
    return [BudgetOut.model_validate(b) for b in result.scalars().all()]


@router.put("/{category}", response_model=BudgetOut)
async def upsert_budget(
    category: str,
    payload: BudgetUpsert,
    current_user: CurrentUser,
    db: DbSession,
) -> BudgetOut:
    result = await db.execute(
        select(Budget).where(
            Budget.user_id == current_user.id, Budget.category == category
        )
    )
    budget = result.scalar_one_or_none()
    if budget is None:
        budget = Budget(
            user_id=current_user.id,
            category=category,
            monthly_limit=payload.monthly_limit,
        )
        db.add(budget)
    else:
        budget.monthly_limit = payload.monthly_limit
    await db.commit()
    await db.refresh(budget)
    return BudgetOut.model_validate(budget)


@router.delete("/{category}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget(
    category: str, current_user: CurrentUser, db: DbSession
) -> None:
    result = await db.execute(
        select(Budget).where(
            Budget.user_id == current_user.id, Budget.category == category
        )
    )
    budget = result.scalar_one_or_none()
    if budget is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="budget_not_found"
        )
    await db.delete(budget)
    await db.commit()


@router.get("/status", response_model=BudgetStatusResponse)
async def budgets_status(
    current_user: CurrentUser,
    db: DbSession,
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
) -> BudgetStatusResponse:
    resolved_month = month or current_month_local()
    month_clauses = month_filter(resolved_month)

    budgets_result = await db.execute(
        select(Budget).where(Budget.user_id == current_user.id).order_by(Budget.category)
    )
    budgets = budgets_result.scalars().all()

    spent_rows = await db.execute(
        select(
            Transaction.category,
            func.coalesce(func.sum(Transaction.amount), 0).label("total"),
        )
        .where(
            Transaction.user_id == current_user.id,
            Transaction.transaction_type == TransactionType.debit,
            *month_clauses,
        )
        .group_by(Transaction.category)
    )
    spent_by_category: dict[str | None, Decimal] = {
        row.category: Decimal(row.total) for row in spent_rows.all()
    }

    items = []
    for budget in budgets:
        spent = spent_by_category.get(budget.category, Decimal("0"))
        items.append(
            BudgetStatusItem(
                category=budget.category,
                monthly_limit=budget.monthly_limit,
                spent=spent,
                pct=budget_pct(spent, budget.monthly_limit),
                status=budget_alert_status(spent, budget.monthly_limit),
            )
        )

    return BudgetStatusResponse(month=resolved_month, items=items)
