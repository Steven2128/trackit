"""Debt payoff strategy simulator: avalanche vs snowball.

Pure, DB-free core — same shape as `subscription_detector.py` so it's
unit-testable without a database. The thin DB wrapper lives in
`app/api/routes/debts.py` (`GET /debts/strategy`).

No persisted state — recomputed from the `debts` table on every request.

Simulation: month by month, every live debt accrues interest (EA rate
converted to effective monthly), then payments are applied. The total
monthly budget is constant — sum of all original minimum payments plus the
user's extra — so when a debt dies, its minimum "rolls over" into the
target debt (the classic rollover both strategies rely on):

- avalanche: extra goes to the highest interest rate first (cheapest in
  total interest, mathematically optimal).
- snowball: extra goes to the smallest balance first (fastest first win,
  better for motivation).

A debt whose payment doesn't even cover its monthly interest never
converges; the simulation caps at MAX_MONTHS and flags it instead of
looping forever.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

MAX_MONTHS = 600

_CENT = Decimal("0.01")


@dataclass
class DebtLike:
    name: str
    balance: Decimal
    annual_rate: Decimal | None  # EA percent, e.g. Decimal("45.5"); None -> 0
    minimum_payment: Decimal | None  # None -> 0


@dataclass
class DebtPayoff:
    name: str
    payoff_month: int | None  # months from now (1-based); None if it never converges
    interest_paid: Decimal


@dataclass
class StrategyResult:
    strategy: str  # "avalanche" | "snowball"
    months_to_free: int | None  # None if any debt never converges
    total_interest: Decimal
    total_paid: Decimal
    payoff_order: list[str]  # priority order the strategy targets debts in
    per_debt: list[DebtPayoff]
    converges: bool


@dataclass
class StrategyComparison:
    avalanche: StrategyResult
    snowball: StrategyResult
    interest_saved_by_avalanche: Decimal  # snowball interest - avalanche interest
    months_saved_by_avalanche: int | None  # None when either doesn't converge
    recommended: str  # "avalanche" | "snowball"


def _monthly_rate(annual_rate: Decimal | None) -> Decimal:
    """EA percent -> effective monthly rate. (1+EA)^(1/12) - 1.

    Decimal has no fractional exponent; float precision is more than enough
    for a payoff projection.
    """
    if annual_rate is None or annual_rate <= 0:
        return Decimal("0")
    monthly = (1.0 + float(annual_rate) / 100.0) ** (1.0 / 12.0) - 1.0
    return Decimal(str(monthly))


def _priority(debts: list[DebtLike], strategy: str) -> list[DebtLike]:
    if strategy == "avalanche":
        # Highest rate first; tie-break on smaller balance for a quicker win.
        return sorted(
            debts,
            key=lambda d: (-(d.annual_rate or Decimal("0")), d.balance),
        )
    # snowball: smallest balance first; tie-break on higher rate.
    return sorted(
        debts,
        key=lambda d: (d.balance, -(d.annual_rate or Decimal("0"))),
    )


def simulate_strategy(
    debts: list[DebtLike],
    extra_monthly: Decimal,
    strategy: str,
) -> StrategyResult:
    ordered = _priority([d for d in debts if d.balance > 0], strategy)
    payoff_order = [d.name for d in ordered]

    balances = {id(d): d.balance for d in ordered}
    interest_paid = {id(d): Decimal("0") for d in ordered}
    payoff_month: dict[int, int | None] = {id(d): None for d in ordered}
    rates = {id(d): _monthly_rate(d.annual_rate) for d in ordered}

    # Constant total budget: all original minimums + extra. Dead debts'
    # minimums roll over into the target automatically.
    budget = sum((d.minimum_payment or Decimal("0") for d in ordered), Decimal("0"))
    budget += extra_monthly

    total_paid = Decimal("0")
    month = 0
    while month < MAX_MONTHS and any(b > 0 for b in balances.values()):
        month += 1

        # 1. Accrue interest on every live debt.
        for d in ordered:
            if balances[id(d)] <= 0:
                continue
            interest = (balances[id(d)] * rates[id(d)]).quantize(_CENT)
            balances[id(d)] += interest
            interest_paid[id(d)] += interest

        # 2. Minimum payment on every live debt (capped at its balance).
        available = budget
        for d in ordered:
            if balances[id(d)] <= 0:
                continue
            payment = min(d.minimum_payment or Decimal("0"), balances[id(d)], available)
            balances[id(d)] -= payment
            available -= payment
            total_paid += payment

        # 3. Whatever's left goes to the first live debt in priority order,
        #    cascading to the next when it dies mid-month.
        for d in ordered:
            if available <= 0:
                break
            if balances[id(d)] <= 0:
                continue
            payment = min(available, balances[id(d)])
            balances[id(d)] -= payment
            available -= payment
            total_paid += payment

        for d in ordered:
            if balances[id(d)] <= 0 and payoff_month[id(d)] is None:
                payoff_month[id(d)] = month

    converges = all(b <= 0 for b in balances.values())
    total_interest = sum(interest_paid.values(), Decimal("0"))
    # Interest accrued on a debt that never converges is noise, but keep it —
    # it shows the user how fast the hole is deepening.

    return StrategyResult(
        strategy=strategy,
        months_to_free=month if converges else None,
        total_interest=total_interest.quantize(_CENT),
        total_paid=total_paid.quantize(_CENT),
        payoff_order=payoff_order,
        per_debt=[
            DebtPayoff(
                name=d.name,
                payoff_month=payoff_month[id(d)],
                interest_paid=interest_paid[id(d)].quantize(_CENT),
            )
            for d in ordered
        ],
        converges=converges,
    )


def compare_strategies(
    debts: list[DebtLike],
    extra_monthly: Decimal,
) -> StrategyComparison:
    avalanche = simulate_strategy(debts, extra_monthly, "avalanche")
    snowball = simulate_strategy(debts, extra_monthly, "snowball")

    interest_saved = snowball.total_interest - avalanche.total_interest
    months_saved = (
        snowball.months_to_free - avalanche.months_to_free
        if snowball.months_to_free is not None and avalanche.months_to_free is not None
        else None
    )

    # Avalanche when it actually saves money; when both cost the same
    # (identical rates, single debt), snowball's early wins take it.
    recommended = "avalanche" if interest_saved > 0 else "snowball"

    return StrategyComparison(
        avalanche=avalanche,
        snowball=snowball,
        interest_saved_by_avalanche=interest_saved.quantize(_CENT),
        months_saved_by_avalanche=months_saved,
        recommended=recommended,
    )
