"""Weekly spending digest — pure render core + thin DB wrapper, same split
as `budget_status.py` / `transfer_matcher.py`. No persisted state: recomputed
from `transactions` each run, like `GET /dashboard`.

Excludes transfers between the user's own accounts and cash withdrawals from
totals — same convention as `GET /transactions/summary`
(`app/api/routes/transactions.py`).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import not_in_excluded
from app.models.transaction import Transaction, TransactionType

EXCLUDED_FROM_SPENT_CATEGORIES = ("transfer", "cash_withdrawal", "debt_payment")
EXCLUDED_FROM_RECEIVED_CATEGORIES = ("transfer", "debt_payment")


@dataclass
class CategoryTotal:
    category: str | None
    total: Decimal
    count: int


@dataclass
class WeeklySummaryData:
    week_start: date
    week_end: date
    total_spent: Decimal
    total_received: Decimal
    by_category: list[CategoryTotal]
    transaction_count: int


def _format_cop(amount: Decimal) -> str:
    """`$1.234.567` — Colombian thousands-dot, no decimals, matches
    `mobile/src/utils/currency.ts`'s `Intl.NumberFormat("es-CO")` output."""
    return f"${amount:,.0f}".replace(",", ".")


def render_weekly_summary_email(data: WeeklySummaryData) -> tuple[str, str]:
    week_label = f"{data.week_start.strftime('%d/%m')} - {data.week_end.strftime('%d/%m/%Y')}"
    subject = f"Tu resumen semanal ({week_label}): {_format_cop(data.total_spent)} gastados"

    rows = "".join(
        f"<tr><td style='padding:4px 8px'>{item.category or 'Sin categoría'}</td>"
        f"<td style='padding:4px 8px;text-align:right'>{_format_cop(item.total)}</td>"
        f"<td style='padding:4px 8px;text-align:right'>{item.count}</td></tr>"
        for item in data.by_category
    )
    if not rows:
        rows = "<tr><td colspan='3' style='padding:8px'>Sin gastos esta semana.</td></tr>"

    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:0 auto">
      <h2>Resumen semanal — {week_label}</h2>
      <p><strong>Gastado:</strong> {_format_cop(data.total_spent)}</p>
      <p><strong>Recibido:</strong> {_format_cop(data.total_received)}</p>
      <p><strong>Transacciones:</strong> {data.transaction_count}</p>
      <table style="width:100%;border-collapse:collapse">
        <thead>
          <tr>
            <th style="text-align:left;padding:4px 8px">Categoría</th>
            <th style="text-align:right;padding:4px 8px">Total</th>
            <th style="text-align:right;padding:4px 8px">#</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    """
    return subject, html


async def build_weekly_summary(
    db: AsyncSession,
    user_id: uuid.UUID,
    week_start_at: datetime,
    week_end_at: datetime,
    week_start_date: date,
    week_end_date: date,
) -> WeeklySummaryData:
    base_filter = [
        Transaction.user_id == user_id,
        Transaction.occurred_at >= week_start_at,
        Transaction.occurred_at < week_end_at,
    ]

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
        CategoryTotal(category=row.category, total=Decimal(row.total), count=row.count)
        for row in by_category_rows.all()
    ]

    count_result = await db.execute(
        select(func.count()).select_from(Transaction).where(*base_filter)
    )
    transaction_count = count_result.scalar_one()

    return WeeklySummaryData(
        week_start=week_start_date,
        week_end=week_end_date,
        total_spent=total_spent,
        total_received=total_received,
        by_category=by_category,
        transaction_count=transaction_count,
    )


async def _sum_amount(db: AsyncSession, filters: list) -> Decimal:
    result = await db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(*filters)
    )
    value = result.scalar_one()
    return Decimal(value) if not isinstance(value, Decimal) else value
