from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.services.cash_flow import UpcomingPayment
from app.services.push_alerts import BudgetSnapshot, build_alerts
from app.services.spending_anomalies import SpendingAnomaly

MONTH = "2026-07"


def _budget(category: str, spent: str, limit: str) -> BudgetSnapshot:
    return BudgetSnapshot(
        category=category, spent=Decimal(spent), monthly_limit=Decimal(limit)
    )


def _upcoming(
    name: str,
    amount: str,
    deadline: date | None,
    days_left: int | None,
    is_debt: bool = False,
) -> UpcomingPayment:
    return UpcomingPayment(
        name=name,
        amount=Decimal(amount),
        deadline=deadline,
        days_left=days_left,
        is_debt_payment=is_debt,
    )


class TestBudgetAlerts:
    def test_ok_budget_is_silent(self) -> None:
        alerts = build_alerts(MONTH, [_budget("comida", "100000", "500000")], [], [])
        assert alerts == []

    def test_warning_at_80_pct(self) -> None:
        alerts = build_alerts(MONTH, [_budget("comida", "400000", "500000")], [], [])
        assert len(alerts) == 1
        assert alerts[0].dedupe_key == "budget:2026-07:comida:warning"
        assert "80" in alerts[0].title

    def test_exceeded_at_100_pct(self) -> None:
        alerts = build_alerts(MONTH, [_budget("comida", "500000", "500000")], [], [])
        assert alerts[0].dedupe_key == "budget:2026-07:comida:exceeded"
        assert "superado" in alerts[0].title

    def test_money_formatted_colombian_style(self) -> None:
        alerts = build_alerts(MONTH, [_budget("comida", "1234567", "500000")], [], [])
        assert "$1.234.567" in alerts[0].body


class TestDeadlineAlerts:
    def test_within_three_days_alerts(self) -> None:
        alerts = build_alerts(
            MONTH, [], [_upcoming("Arriendo", "900000", date(2026, 7, 17), 3)], []
        )
        assert alerts[0].dedupe_key == "deadline:Arriendo:2026-07-17"
        assert "vence en 3 días" in alerts[0].title

    def test_today_and_tomorrow_wording(self) -> None:
        today = build_alerts(
            MONTH, [], [_upcoming("Tarjeta", "100000", date(2026, 7, 14), 0)], []
        )
        tomorrow = build_alerts(
            MONTH, [], [_upcoming("Tarjeta", "100000", date(2026, 7, 15), 1)], []
        )
        assert "vence hoy" in today[0].title
        assert "vence mañana" in tomorrow[0].title

    def test_far_deadline_is_silent(self) -> None:
        alerts = build_alerts(
            MONTH, [], [_upcoming("Arriendo", "900000", date(2026, 7, 30), 16)], []
        )
        assert alerts == []

    def test_overdue_is_silent(self) -> None:
        alerts = build_alerts(
            MONTH, [], [_upcoming("Arriendo", "900000", date(2026, 7, 10), -4)], []
        )
        assert alerts == []

    def test_no_deadline_is_silent(self) -> None:
        alerts = build_alerts(MONTH, [], [_upcoming("Apartado", "50000", None, None)], [])
        assert alerts == []

    def test_debt_payment_flagged_in_body(self) -> None:
        alerts = build_alerts(
            MONTH,
            [],
            [_upcoming("Tarjeta Itaú", "300000", date(2026, 7, 16), 2, is_debt=True)],
            [],
        )
        assert "pago de deuda" in alerts[0].body


class TestAnomalyAlerts:
    def test_anomaly_produces_alert(self) -> None:
        anomaly = SpendingAnomaly(
            category="transporte",
            current=Decimal("300000"),
            historical_avg=Decimal("120000"),
            ratio=Decimal("2.50"),
        )
        alerts = build_alerts(MONTH, [], [], [anomaly])
        assert alerts[0].dedupe_key == "unusual:2026-07:transporte"
        assert "2.50×" in alerts[0].body


def test_all_sources_combined_and_keys_unique() -> None:
    alerts = build_alerts(
        MONTH,
        [_budget("comida", "600000", "500000")],
        [_upcoming("Arriendo", "900000", date(2026, 7, 16), 2)],
        [
            SpendingAnomaly(
                category="comida",
                current=Decimal("600000"),
                historical_avg=Decimal("200000"),
                ratio=Decimal("3.00"),
            )
        ],
    )
    keys = [a.dedupe_key for a in alerts]
    assert len(alerts) == 3
    assert len(set(keys)) == 3
