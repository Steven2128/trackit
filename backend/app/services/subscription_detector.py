"""Detect recurring charges (subscriptions) from transaction history.

Pure, DB-free core — mirrors the `pair_transfers` (`transfer_matcher.py`) /
`budget_pct` (`budget_status.py`) shape so it's unit-testable without a
database. The thin DB wrapper lives in `app/api/routes/subscriptions.py`.

Detection has no persisted state (no table, no migration) — like
`GET /dashboard`, it's recomputed from `transactions` on every request.

Algorithm: group by normalized merchant, cluster by amount (±10% — same
merchant can sell different things at different prices), then check whether
every gap between consecutive occurrences (sorted by date) falls inside one
known cadence window. A cluster only counts as a subscription if *all* its
gaps agree on the same cadence — one outlier gap means it's not recurring
enough to flag, favoring precision over recall.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

AMOUNT_TOLERANCE = Decimal("0.10")

# (label, min_days, max_days) — ranges are disjoint, so a gap matches at
# most one cadence.
_CADENCES: list[tuple[str, int, int]] = [
    ("weekly", 6, 8),
    ("biweekly", 12, 16),
    ("monthly", 27, 33),
    ("yearly", 350, 380),
]


@dataclass
class TransactionLike:
    merchant: str | None
    amount: Decimal
    category: str | None
    occurred_at: datetime


@dataclass
class DetectedSubscription:
    merchant: str
    category: str | None
    average_amount: Decimal
    frequency: str
    occurrences: int
    last_occurred_at: datetime
    next_expected_at: datetime


def _normalize_merchant(merchant: str) -> str:
    nfkd = unicodedata.normalize("NFKD", merchant)
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    return " ".join(stripped.lower().split())


def _cluster_by_amount(transactions: list[TransactionLike]) -> list[list[TransactionLike]]:
    """Greedy clustering: sort by amount, start a new cluster whenever the
    next amount drifts more than AMOUNT_TOLERANCE from the running average."""
    ordered = sorted(transactions, key=lambda t: t.amount)
    clusters: list[list[TransactionLike]] = []
    for tx in ordered:
        if clusters:
            current = clusters[-1]
            avg = sum((t.amount for t in current), Decimal("0")) / len(current)
            if avg > 0 and abs(tx.amount - avg) / avg <= AMOUNT_TOLERANCE:
                current.append(tx)
                continue
        clusters.append([tx])
    return clusters


def _cadence_for_gaps(gaps: list[int]) -> str | None:
    for label, lo, hi in _CADENCES:
        if all(lo <= gap <= hi for gap in gaps):
            return label
    return None


def _most_common_category(transactions: list[TransactionLike]) -> str | None:
    counts: dict[str, int] = {}
    for t in transactions:
        if t.category:
            counts[t.category] = counts.get(t.category, 0) + 1
    if not counts:
        return None
    return max(counts.items(), key=lambda kv: kv[1])[0]


def detect_subscriptions(
    transactions: list[TransactionLike],
    *,
    min_occurrences: int = 2,
) -> list[DetectedSubscription]:
    by_merchant: dict[str, list[TransactionLike]] = {}
    for tx in transactions:
        if not tx.merchant:
            continue
        by_merchant.setdefault(_normalize_merchant(tx.merchant), []).append(tx)

    detected: list[DetectedSubscription] = []
    for group in by_merchant.values():
        for cluster in _cluster_by_amount(group):
            if len(cluster) < min_occurrences:
                continue
            ordered = sorted(cluster, key=lambda t: t.occurred_at)
            gaps = [
                (ordered[i + 1].occurred_at - ordered[i].occurred_at).days
                for i in range(len(ordered) - 1)
            ]
            frequency = _cadence_for_gaps(gaps)
            if frequency is None:
                continue

            average_amount = sum((t.amount for t in ordered), Decimal("0")) / len(ordered)
            avg_gap_days = round(sum(gaps) / len(gaps))
            last_occurred_at = ordered[-1].occurred_at

            detected.append(
                DetectedSubscription(
                    merchant=ordered[-1].merchant or "",
                    category=_most_common_category(ordered),
                    average_amount=average_amount.quantize(Decimal("0.01")),
                    frequency=frequency,
                    occurrences=len(ordered),
                    last_occurred_at=last_occurred_at,
                    next_expected_at=last_occurred_at + timedelta(days=avg_gap_days),
                )
            )

    detected.sort(key=lambda d: d.next_expected_at)
    return detected
