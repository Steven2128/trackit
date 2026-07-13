from __future__ import annotations

from decimal import Decimal

from app.services.health_score import compute_health_score


def _score(**overrides):
    defaults = dict(
        has_debts=False,
        total_minimum_payments=Decimal("0"),
        monthly_income=Decimal("3374000"),
        budget_count=0,
        budget_warning_count=0,
        budget_exceeded_count=0,
        goal_pcts=[],
        anomaly_count=0,
    )
    defaults.update(overrides)
    return compute_health_score(**defaults)


class TestHealthScore:
    def test_perfect_score(self) -> None:
        result = _score(
            budget_count=3,
            goal_pcts=[100, 100],
        )

        assert result.debt == 30
        assert result.budgets == 25
        assert result.savings == 25
        assert result.anomalies == 20
        assert result.total == 100

    def test_debt_free_gets_full_debt_credit(self) -> None:
        assert _score().debt == 30

    def test_light_debt_burden(self) -> None:
        # 800k minimums on 3.37M income ~ 24% -> light burden.
        result = _score(
            has_debts=True,
            total_minimum_payments=Decimal("800000"),
        )
        assert result.debt == 20

    def test_heavy_debt_burden(self) -> None:
        # 2M minimums on 3.37M income ~ 59% -> heavy.
        result = _score(
            has_debts=True,
            total_minimum_payments=Decimal("2000000"),
        )
        assert result.debt == 0

    def test_debt_with_unknown_income_is_neutral(self) -> None:
        result = _score(
            has_debts=True,
            total_minimum_payments=Decimal("800000"),
            monthly_income=None,
        )
        assert result.debt == 15

    def test_budget_overruns_subtract(self) -> None:
        result = _score(budget_count=3, budget_warning_count=1, budget_exceeded_count=1)
        assert result.budgets == 10  # 25 - 5 - 10

    def test_budget_floor_at_zero(self) -> None:
        result = _score(budget_count=5, budget_exceeded_count=5)
        assert result.budgets == 0

    def test_no_budgets_is_neutral(self) -> None:
        assert _score().budgets == 12

    def test_savings_average_progress(self) -> None:
        result = _score(goal_pcts=[50, 100])
        assert result.savings == 19  # 75% of 25

    def test_no_goals_is_neutral(self) -> None:
        assert _score().savings == 10

    def test_anomalies_subtract(self) -> None:
        assert _score(anomaly_count=2).anomalies == 6  # 20 - 14

    def test_anomaly_floor_at_zero(self) -> None:
        assert _score(anomaly_count=5).anomalies == 0

    def test_total_is_component_sum(self) -> None:
        result = _score(
            has_debts=True,
            total_minimum_payments=Decimal("800000"),
            budget_count=2,
            budget_warning_count=1,
            goal_pcts=[40],
            anomaly_count=1,
        )
        assert result.total == result.debt + result.budgets + result.savings + result.anomalies
