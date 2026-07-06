"""Pure budget-alert math, kept out of the route so it can be unit-tested
without a database.

Thresholds: below 80% of the limit is "ok", 80% to under 100% is "warning",
100% and above is "exceeded".
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

WARNING_THRESHOLD = Decimal("0.80")

BudgetAlertStatus = str  # "ok" | "warning" | "exceeded"


def budget_pct(spent: Decimal, limit: Decimal) -> Decimal:
    """Spent as a percentage of the limit, 1 decimal place. A zero/negative
    limit reports 100% when anything was spent (misconfigured budget should
    scream, not divide by zero)."""
    if limit <= 0:
        return Decimal("100.0") if spent > 0 else Decimal("0.0")
    pct = spent / limit * 100
    return pct.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def budget_alert_status(spent: Decimal, limit: Decimal) -> BudgetAlertStatus:
    if limit <= 0:
        return "exceeded" if spent > 0 else "ok"
    ratio = spent / limit
    if ratio >= 1:
        return "exceeded"
    if ratio >= WARNING_THRESHOLD:
        return "warning"
    return "ok"
