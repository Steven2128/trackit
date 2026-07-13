from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.services.cash_flow import (
    IncomeLike,
    PaymentLike,
    compute_cash_flow,
)

TODAY = date(2026, 7, 13)


def _income(name: str, amount: str, day: int) -> IncomeLike:
    return IncomeLike(name=name, amount=Decimal(amount), expected_day=day)


def _payment(
    name: str,
    amount: str,
    due_day: int | None = None,
    grace_days: int = 0,
    is_debt: bool = False,
) -> PaymentLike:
    return PaymentLike(
        name=name,
        amount=Decimal(amount),
        due_day=due_day,
        grace_days=grace_days,
        is_debt_payment=is_debt,
    )


class TestComputeCashFlow:
    def test_available_is_income_minus_committed(self) -> None:
        incomes = [_income("Quincena 1", "1136548", 5), _income("Quincena 2", "1186548", 20)]
        payments = [_payment("Arriendo", "850000", due_day=24), _payment("TC", "800000", due_day=16)]

        result = compute_cash_flow(incomes, payments, TODAY)

        assert result.monthly_income == Decimal("2323096")
        assert result.monthly_committed == Decimal("1650000")
        assert result.available == Decimal("673096")

    def test_next_income_is_nearest_future_occurrence(self) -> None:
        incomes = [_income("Quincena 1", "1000", 5), _income("Quincena 2", "2000", 20)]

        result = compute_cash_flow(incomes, [], TODAY)

        # Today is the 13th: day 5 already passed -> next is the 20th.
        assert result.next_income_date == date(2026, 7, 20)
        assert result.next_income_name == "Quincena 2"
        assert result.next_income_amount == Decimal("2000")

    def test_income_today_counts_as_next(self) -> None:
        incomes = [_income("Pago", "1000", 13)]

        result = compute_cash_flow(incomes, [], TODAY)

        assert result.next_income_date == TODAY

    def test_passed_day_rolls_to_next_month(self) -> None:
        incomes = [_income("Pago", "1000", 5)]

        result = compute_cash_flow(incomes, [], TODAY)

        assert result.next_income_date == date(2026, 8, 5)

    def test_day_31_clamps_to_month_end(self) -> None:
        # September has 30 days: day 31 must land on the 30th, not October 1st.
        incomes = [_income("Pago", "1000", 31)]

        result = compute_cash_flow(incomes, [], date(2026, 9, 1))

        assert result.next_income_date == date(2026, 9, 30)

    def test_december_rolls_to_january(self) -> None:
        incomes = [_income("Pago", "1000", 5)]

        result = compute_cash_flow(incomes, [], date(2026, 12, 20))

        assert result.next_income_date == date(2027, 1, 5)

    def test_deadline_includes_grace_days(self) -> None:
        # Rent: cut on the 24th + 15 grace days -> real deadline Aug 8.
        payments = [_payment("Arriendo", "1400000", due_day=24, grace_days=15)]

        result = compute_cash_flow([], payments, TODAY)

        assert result.upcoming[0].deadline == date(2026, 8, 8)
        assert result.upcoming[0].days_left == 26

    def test_upcoming_sorted_by_deadline_none_last(self) -> None:
        payments = [
            _payment("Sin fecha", "100"),
            _payment("Cerca", "100", due_day=15),
            _payment("Lejos", "100", due_day=28),
        ]

        result = compute_cash_flow([], payments, TODAY)

        assert [u.name for u in result.upcoming] == ["Cerca", "Lejos", "Sin fecha"]

    def test_checklist_puts_debts_first(self) -> None:
        payments = [
            _payment("Arriendo", "850000", due_day=14),
            _payment("TC Itau", "800000", due_day=28, is_debt=True),
        ]

        result = compute_cash_flow([], payments, TODAY)

        # Rent is due sooner, but the pay-first rule puts debt at the top.
        assert [u.name for u in result.checklist] == ["TC Itau", "Arriendo"]
        # Plain upcoming stays deadline-ordered.
        assert [u.name for u in result.upcoming] == ["Arriendo", "TC Itau"]

    def test_empty_inputs(self) -> None:
        result = compute_cash_flow([], [], TODAY)

        assert result.monthly_income == Decimal("0")
        assert result.available == Decimal("0")
        assert result.next_income_date is None
        assert result.upcoming == []
        assert result.checklist == []
