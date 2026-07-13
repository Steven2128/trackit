from __future__ import annotations

from decimal import Decimal

from app.services.debt_strategy import (
    MAX_MONTHS,
    DebtLike,
    compare_strategies,
    simulate_strategy,
)


def _debt(
    name: str,
    balance: str,
    rate: str | None = None,
    minimum: str | None = None,
) -> DebtLike:
    return DebtLike(
        name=name,
        balance=Decimal(balance),
        annual_rate=Decimal(rate) if rate is not None else None,
        minimum_payment=Decimal(minimum) if minimum is not None else None,
    )


class TestSimulateStrategy:
    def test_single_zero_rate_debt_pays_off_linearly(self) -> None:
        debts = [_debt("TC", "1000000", rate=None, minimum="100000")]

        result = simulate_strategy(debts, Decimal("0"), "avalanche")

        assert result.converges
        assert result.months_to_free == 10
        assert result.total_interest == Decimal("0.00")
        assert result.total_paid == Decimal("1000000.00")

    def test_extra_payment_shortens_payoff(self) -> None:
        debts = [_debt("TC", "1000000", rate=None, minimum="100000")]

        result = simulate_strategy(debts, Decimal("100000"), "avalanche")

        assert result.months_to_free == 5

    def test_interest_accrues_before_payment(self) -> None:
        # 12.68% EA ~ 1% monthly: first month interest ~10000 on 1M.
        debts = [_debt("TC", "1000000", rate="12.68", minimum="1010000")]

        result = simulate_strategy(debts, Decimal("0"), "avalanche")

        assert result.months_to_free == 1
        assert result.total_interest > Decimal("9900")
        assert result.total_interest < Decimal("10100")

    def test_avalanche_targets_highest_rate_first(self) -> None:
        debts = [
            _debt("Barata", "500000", rate="10", minimum="50000"),
            _debt("Cara", "500000", rate="60", minimum="50000"),
        ]

        result = simulate_strategy(debts, Decimal("200000"), "avalanche")

        assert result.payoff_order == ["Cara", "Barata"]
        cara = next(p for p in result.per_debt if p.name == "Cara")
        barata = next(p for p in result.per_debt if p.name == "Barata")
        assert cara.payoff_month is not None and barata.payoff_month is not None
        assert cara.payoff_month < barata.payoff_month

    def test_snowball_targets_smallest_balance_first(self) -> None:
        debts = [
            _debt("Grande", "2000000", rate="60", minimum="100000"),
            _debt("Chica", "200000", rate="10", minimum="20000"),
        ]

        result = simulate_strategy(debts, Decimal("100000"), "snowball")

        assert result.payoff_order == ["Chica", "Grande"]
        chica = next(p for p in result.per_debt if p.name == "Chica")
        # Month 1 Chica gets its 20k minimum + 100k extra = 120k against
        # ~201.6k (balance + interest); month 2 finishes it.
        assert chica.payoff_month == 2

    def test_rollover_keeps_total_budget_constant(self) -> None:
        # After debt A dies, its minimum keeps flowing into debt B.
        debts = [
            _debt("A", "100000", rate=None, minimum="100000"),
            _debt("B", "500000", rate=None, minimum="100000"),
        ]

        result = simulate_strategy(debts, Decimal("0"), "avalanche")

        # 200k/month against 600k total -> 3 months, not 1 + 4.
        assert result.months_to_free == 3

    def test_payment_below_interest_never_converges(self) -> None:
        # ~3.4% monthly interest on 1M ~ 34k > 10k payment: hole deepens.
        debts = [_debt("TC", "1000000", rate="50", minimum="10000")]

        result = simulate_strategy(debts, Decimal("0"), "avalanche")

        assert not result.converges
        assert result.months_to_free is None
        assert result.per_debt[0].payoff_month is None

    def test_no_debts_converges_immediately(self) -> None:
        result = simulate_strategy([], Decimal("100000"), "avalanche")

        assert result.converges
        assert result.months_to_free == 0
        assert result.per_debt == []

    def test_capped_at_max_months(self) -> None:
        debts = [_debt("TC", "1000000", rate="50", minimum="10000")]

        result = simulate_strategy(debts, Decimal("0"), "snowball")

        assert not result.converges
        # The loop must stop at the cap, not spin forever.
        assert MAX_MONTHS == 600


class TestCompareStrategies:
    def test_avalanche_recommended_when_rates_differ(self) -> None:
        debts = [
            _debt("Cara", "1000000", rate="60", minimum="50000"),
            _debt("Barata chica", "300000", rate="5", minimum="30000"),
        ]

        comparison = compare_strategies(debts, Decimal("100000"))

        assert comparison.recommended == "avalanche"
        assert comparison.interest_saved_by_avalanche > 0
        assert (
            comparison.avalanche.total_interest < comparison.snowball.total_interest
        )

    def test_snowball_recommended_when_no_interest_difference(self) -> None:
        debts = [
            _debt("A", "500000", rate="20", minimum="50000"),
            _debt("B", "500000", rate="20", minimum="50000"),
        ]

        comparison = compare_strategies(debts, Decimal("100000"))

        # Same rate everywhere: avalanche saves nothing, early wins take it.
        assert comparison.recommended == "snowball"

    def test_months_saved_none_when_not_converging(self) -> None:
        debts = [_debt("TC", "1000000", rate="80", minimum="1000")]

        comparison = compare_strategies(debts, Decimal("0"))

        assert comparison.months_saved_by_avalanche is None
        assert not comparison.avalanche.converges
