"""Financial health score: 0-100 from four explainable components.

Pure, DB-free core. The DB wrapper lives in `app/api/routes/insights.py`.

Components (weights sum to 100):
- debt (30): debt-free is best; otherwise scored by how much of monthly
  income the minimum payments eat. Unknown income -> neutral half credit.
- budgets (25): full when every budget is under 80%; warnings and overruns
  subtract. No budgets configured -> neutral half credit.
- savings (25): average progress across goals. No goals -> neutral 10.
- anomalies (20): full when this month has no unusual spending spikes.

The score improves when the user pays down debt and saves — the two
behaviors the roadmap says it should reward.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class HealthScoreBreakdown:
    debt: int  # 0-30
    budgets: int  # 0-25
    savings: int  # 0-25
    anomalies: int  # 0-20
    total: int  # 0-100


def _debt_component(
    total_minimum_payments: Decimal,
    monthly_income: Decimal | None,
    has_debts: bool,
) -> int:
    if not has_debts:
        return 30
    if monthly_income is None or monthly_income <= 0:
        return 15  # can't judge the load; neutral
    burden = total_minimum_payments / monthly_income
    if burden <= Decimal("0.30"):
        return 20
    if burden <= Decimal("0.50"):
        return 10
    return 0


def _budget_component(warning_count: int, exceeded_count: int, budget_count: int) -> int:
    if budget_count == 0:
        return 12  # not configured; neutral
    return max(0, 25 - warning_count * 5 - exceeded_count * 10)


def _savings_component(goal_pcts: list[int]) -> int:
    if not goal_pcts:
        return 10  # no goals yet; neutral
    avg = sum(goal_pcts) / len(goal_pcts)
    return round(avg * 25 / 100)


def _anomaly_component(anomaly_count: int) -> int:
    return max(0, 20 - anomaly_count * 7)


def compute_health_score(
    *,
    has_debts: bool,
    total_minimum_payments: Decimal,
    monthly_income: Decimal | None,
    budget_count: int,
    budget_warning_count: int,
    budget_exceeded_count: int,
    goal_pcts: list[int],
    anomaly_count: int,
) -> HealthScoreBreakdown:
    debt = _debt_component(total_minimum_payments, monthly_income, has_debts)
    budgets = _budget_component(budget_warning_count, budget_exceeded_count, budget_count)
    savings = _savings_component(goal_pcts)
    anomalies = _anomaly_component(anomaly_count)
    return HealthScoreBreakdown(
        debt=debt,
        budgets=budgets,
        savings=savings,
        anomalies=anomalies,
        total=debt + budgets + savings + anomalies,
    )
