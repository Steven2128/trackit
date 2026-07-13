from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.services.subscription_detector import TransactionLike, detect_subscriptions

BASE = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _tx(
    days_offset: int,
    amount: str,
    merchant: str = "Netflix",
    category: str | None = "subscriptions",
) -> TransactionLike:
    return TransactionLike(
        merchant=merchant,
        amount=Decimal(amount),
        category=category,
        occurred_at=BASE + timedelta(days=days_offset),
    )


class TestDetectSubscriptions:
    def test_monthly_charge_detected(self) -> None:
        txs = [_tx(0, "39900"), _tx(30, "39900"), _tx(60, "39900")]

        detected = detect_subscriptions(txs)

        assert len(detected) == 1
        sub = detected[0]
        assert sub.merchant == "Netflix"
        assert sub.frequency == "monthly"
        assert sub.occurrences == 3
        assert sub.average_amount == Decimal("39900.00")
        assert sub.last_occurred_at == BASE + timedelta(days=60)
        assert sub.next_expected_at == BASE + timedelta(days=90)

    def test_two_occurrences_meet_default_minimum(self) -> None:
        txs = [_tx(0, "9900"), _tx(30, "9900")]

        detected = detect_subscriptions(txs)

        assert len(detected) == 1
        assert detected[0].occurrences == 2

    def test_erratic_gaps_not_detected(self) -> None:
        txs = [_tx(0, "20000"), _tx(15, "20000"), _tx(55, "20000")]

        detected = detect_subscriptions(txs)

        assert detected == []

    def test_very_different_amounts_split_into_singleton_clusters(self) -> None:
        """Same merchant, wildly different amounts (e.g. one-off purchases) —
        each cluster only has one transaction, below min_occurrences."""
        txs = [_tx(0, "10000"), _tx(30, "500000")]

        detected = detect_subscriptions(txs)

        assert detected == []

    def test_amount_tolerance_still_groups_similar_charges(self) -> None:
        """A subscription price bump within 10% still counts as one series."""
        txs = [_tx(0, "10000"), _tx(30, "10500"), _tx(60, "10800")]

        detected = detect_subscriptions(txs)

        assert len(detected) == 1
        assert detected[0].occurrences == 3

    def test_weekly_cadence_detected(self) -> None:
        txs = [_tx(0, "25000", merchant="Gym"), _tx(7, "25000", merchant="Gym")]

        detected = detect_subscriptions(txs)

        assert len(detected) == 1
        assert detected[0].frequency == "weekly"

    def test_different_merchants_are_independent(self) -> None:
        txs = [
            _tx(0, "39900", merchant="Netflix"),
            _tx(30, "39900", merchant="Netflix"),
            _tx(0, "19900", merchant="Spotify"),
            _tx(30, "19900", merchant="Spotify"),
        ]

        detected = detect_subscriptions(txs)

        assert {d.merchant for d in detected} == {"Netflix", "Spotify"}

    def test_merchant_name_normalization_collapses_accent_and_case(self) -> None:
        txs = [_tx(0, "10000", merchant="Éxito"), _tx(30, "10000", merchant="EXITO")]

        detected = detect_subscriptions(txs)

        assert len(detected) == 1
        assert detected[0].occurrences == 2

    def test_most_common_category_wins(self) -> None:
        txs = [
            _tx(0, "10000", category="shopping"),
            _tx(30, "10000", category="subscriptions"),
            _tx(60, "10000", category="subscriptions"),
        ]

        detected = detect_subscriptions(txs)

        assert detected[0].category == "subscriptions"

    def test_below_min_occurrences_not_detected(self) -> None:
        txs = [_tx(0, "10000")]

        detected = detect_subscriptions(txs, min_occurrences=2)

        assert detected == []

    def test_transactions_without_merchant_are_ignored(self) -> None:
        txs = [_tx(0, "10000", merchant=None), _tx(30, "10000", merchant=None)]  # type: ignore[arg-type]

        detected = detect_subscriptions(txs)

        assert detected == []
