from __future__ import annotations

from decimal import Decimal

from app.services.spending_anomalies import detect_anomalies


def _d(v: str) -> Decimal:
    return Decimal(v)


class TestDetectAnomalies:
    def test_spike_above_threshold_flagged(self) -> None:
        current = {"restaurants": _d("300000")}
        history = {"restaurants": [_d("100000"), _d("120000"), _d("80000")]}

        anomalies = detect_anomalies(current, history)

        assert len(anomalies) == 1
        a = anomalies[0]
        assert a.category == "restaurants"
        assert a.historical_avg == _d("100000.00")
        assert a.ratio == _d("3.00")

    def test_normal_spending_not_flagged(self) -> None:
        current = {"groceries": _d("110000")}
        history = {"groceries": [_d("100000"), _d("120000")]}

        assert detect_anomalies(current, history) == []

    def test_small_amounts_ignored_even_with_big_ratio(self) -> None:
        # 10x jump but under MIN_AMOUNT: noise, not an alert.
        current = {"coffee": _d("40000")}
        history = {"coffee": [_d("4000"), _d("4000")]}

        assert detect_anomalies(current, history) == []

    def test_insufficient_history_not_flagged(self) -> None:
        current = {"travel": _d("900000")}
        history = {"travel": [_d("100000")]}  # only 1 month of baseline

        assert detect_anomalies(current, history) == []

    def test_no_history_at_all_not_flagged(self) -> None:
        current = {"new_category": _d("500000")}

        assert detect_anomalies(current, {}) == []

    def test_sorted_by_ratio_desc(self) -> None:
        current = {"a": _d("200000"), "b": _d("500000")}
        history = {
            "a": [_d("100000"), _d("100000")],  # 2x
            "b": [_d("100000"), _d("100000")],  # 5x
        }

        anomalies = detect_anomalies(current, history)

        assert [a.category for a in anomalies] == ["b", "a"]

    def test_exactly_at_threshold_flagged(self) -> None:
        current = {"x": _d("150000")}
        history = {"x": [_d("100000"), _d("100000")]}

        anomalies = detect_anomalies(current, history)

        assert len(anomalies) == 1
        assert anomalies[0].ratio == _d("1.50")
