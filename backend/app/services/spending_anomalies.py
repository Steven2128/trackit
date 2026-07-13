"""Unusual spending detection: current month vs historical average per category.

Pure, DB-free core (same shape as subscription_detector / cash_flow). The DB
wrapper lives in `app/api/routes/insights.py`.

A category is flagged when ALL of:
- it has at least MIN_HISTORY_MONTHS months with spending in the lookback
  window (no baseline -> no verdict),
- this month's spend exceeds the historical monthly average by RATIO_THRESHOLD,
- this month's spend clears MIN_AMOUNT (a 3x jump on a $10k category is noise).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

RATIO_THRESHOLD = Decimal("1.5")
MIN_AMOUNT = Decimal("50000")  # COP
MIN_HISTORY_MONTHS = 2


@dataclass
class SpendingAnomaly:
    category: str
    current: Decimal
    historical_avg: Decimal
    ratio: Decimal  # current / historical_avg


def detect_anomalies(
    current_by_category: dict[str, Decimal],
    history_by_category: dict[str, list[Decimal]],
    *,
    ratio_threshold: Decimal = RATIO_THRESHOLD,
    min_amount: Decimal = MIN_AMOUNT,
    min_history_months: int = MIN_HISTORY_MONTHS,
) -> list[SpendingAnomaly]:
    """`history_by_category` maps category -> list of monthly totals (one per
    month with spending in the lookback window, current month excluded)."""
    anomalies: list[SpendingAnomaly] = []
    for category, current in current_by_category.items():
        if current < min_amount:
            continue
        history = history_by_category.get(category, [])
        if len(history) < min_history_months:
            continue
        avg = sum(history, Decimal("0")) / len(history)
        if avg <= 0:
            continue
        ratio = current / avg
        if ratio >= ratio_threshold:
            anomalies.append(
                SpendingAnomaly(
                    category=category,
                    current=current,
                    historical_avg=avg.quantize(Decimal("0.01")),
                    ratio=ratio.quantize(Decimal("0.01")),
                )
            )
    anomalies.sort(key=lambda a: a.ratio, reverse=True)
    return anomalies
