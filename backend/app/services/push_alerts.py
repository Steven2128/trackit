"""Build the daily push-alert list for a user.

Pure core (`build_alerts`) in the house style of subscription_detector /
cash_flow: takes plain data, returns `PushAlert`s with a `dedupe_key` that
embeds the month (budgets, anomalies) or the deadline date (payments), so
each alert fires once per period. The `notification_logs` table is what
enforces the "once" — the scheduler job filters against it before sending.

The DB wrapper (`collect_user_alerts`) reuses the exact same queries the
interactive endpoints use, so a push never disagrees with what the app
shows when the user opens it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import current_month_local, month_filter, user_tz
from app.models.budget import Budget
from app.models.income_source import IncomeSource
from app.models.planned_payment import PlannedPayment
from app.models.transaction import Transaction, TransactionType
from app.services.budget_status import budget_alert_status, budget_pct
from app.services.cash_flow import (
    IncomeLike,
    PaymentLike,
    UpcomingPayment,
    compute_cash_flow,
)
from app.services.spending_anomalies import SpendingAnomaly

DEADLINE_ALERT_DAYS = 3


@dataclass
class PushAlert:
    dedupe_key: str
    title: str
    body: str


@dataclass
class BudgetSnapshot:
    category: str
    spent: Decimal
    monthly_limit: Decimal


def _money(amount: Decimal) -> str:
    """COP style: $1.234.567, no decimals."""
    return "$" + f"{amount:,.0f}".replace(",", ".")


def _budget_alerts(month: str, budgets: list[BudgetSnapshot]) -> list[PushAlert]:
    alerts: list[PushAlert] = []
    for b in budgets:
        status = budget_alert_status(b.spent, b.monthly_limit)
        if status == "ok":
            continue
        pct = budget_pct(b.spent, b.monthly_limit)
        if status == "exceeded":
            title = f"🔴 Presupuesto de {b.category} superado"
        else:
            title = f"⚠️ Presupuesto de {b.category} al {pct}%"
        alerts.append(
            PushAlert(
                dedupe_key=f"budget:{month}:{b.category}:{status}",
                title=title,
                body=f"Llevás {_money(b.spent)} de {_money(b.monthly_limit)} este mes.",
            )
        )
    return alerts


def _deadline_alerts(upcoming: list[UpcomingPayment]) -> list[PushAlert]:
    alerts: list[PushAlert] = []
    for p in upcoming:
        if p.deadline is None or p.days_left is None:
            continue
        if not 0 <= p.days_left <= DEADLINE_ALERT_DAYS:
            continue
        if p.days_left == 0:
            when = "vence hoy"
        elif p.days_left == 1:
            when = "vence mañana"
        else:
            when = f"vence en {p.days_left} días"
        alerts.append(
            PushAlert(
                dedupe_key=f"deadline:{p.name}:{p.deadline.isoformat()}",
                title=f"📅 {p.name} {when}",
                body=f"{_money(p.amount)} — límite {p.deadline.strftime('%d/%m')}."
                + (" Es pago de deuda." if p.is_debt_payment else ""),
            )
        )
    return alerts


def _anomaly_alerts(month: str, anomalies: list[SpendingAnomaly]) -> list[PushAlert]:
    return [
        PushAlert(
            dedupe_key=f"unusual:{month}:{a.category}",
            title=f"📈 Gasto inusual en {a.category}",
            body=(
                f"Llevás {_money(a.current)} este mes, "
                f"{a.ratio}× tu promedio de {_money(a.historical_avg)}."
            ),
        )
        for a in anomalies
    ]


def build_alerts(
    month: str,
    budgets: list[BudgetSnapshot],
    upcoming: list[UpcomingPayment],
    anomalies: list[SpendingAnomaly],
) -> list[PushAlert]:
    return (
        _budget_alerts(month, budgets)
        + _deadline_alerts(upcoming)
        + _anomaly_alerts(month, anomalies)
    )


async def collect_user_alerts(db: AsyncSession, user_id) -> list[PushAlert]:
    """Gather this user's current alert set from the same data the
    /budgets/status, /cashflow and /insights endpoints serve."""
    # Local import: routes import services at module load; importing the
    # insights route lazily here avoids a routes<->services import cycle.
    from app.api.routes.insights import _detect_user_anomalies

    month = current_month_local()
    month_clauses = month_filter(month)

    budgets_result = await db.execute(select(Budget).where(Budget.user_id == user_id))
    budgets = budgets_result.scalars().all()
    snapshots: list[BudgetSnapshot] = []
    if budgets:
        spent_rows = await db.execute(
            select(
                Transaction.category,
                func.coalesce(func.sum(Transaction.amount), 0).label("total"),
            )
            .where(
                Transaction.user_id == user_id,
                Transaction.transaction_type == TransactionType.debit,
                *month_clauses,
            )
            .group_by(Transaction.category)
        )
        spent_by_category = {row.category: Decimal(row.total) for row in spent_rows.all()}
        snapshots = [
            BudgetSnapshot(
                category=b.category,
                spent=spent_by_category.get(b.category, Decimal("0")),
                monthly_limit=b.monthly_limit,
            )
            for b in budgets
        ]

    incomes_result = await db.execute(
        select(IncomeSource).where(IncomeSource.user_id == user_id)
    )
    payments_result = await db.execute(
        select(PlannedPayment).where(PlannedPayment.user_id == user_id)
    )
    incomes = [
        IncomeLike(name=i.name, amount=i.amount, expected_day=i.expected_day)
        for i in incomes_result.scalars().all()
    ]
    payments = [
        PaymentLike(
            name=p.name,
            amount=p.amount,
            due_day=p.due_day,
            grace_days=p.grace_days,
            is_debt_payment=p.is_debt_payment,
        )
        for p in payments_result.scalars().all()
    ]
    today = datetime.now(user_tz()).date()
    upcoming = compute_cash_flow(incomes, payments, today).upcoming if payments else []

    _, anomalies = await _detect_user_anomalies(user_id, db)

    return build_alerts(month, snapshots, upcoming, anomalies)
