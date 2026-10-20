"""Stored rows → cash_position inputs. Income amounts mirror the user's real
deposit pattern (two quincenas + a separate bonus); the rest is fictitious."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services.cash_position_sources import (
    Credit,
    DebtPayment,
    debt_obligations,
    default_horizon,
    expected_incomes,
    planned_obligations,
)

Q5 = SimpleNamespace(name="Quincena 5", amount=Decimal("1136548"), expected_day=5)
BONUS = SimpleNamespace(name="Bonificación", amount=Decimal("1050905"), expected_day=8)
Q20 = SimpleNamespace(name="Quincena 20", amount=Decimal("1136548"), expected_day=20)
SOURCES = [Q5, BONUS, Q20]


@pytest.mark.parametrize(
    "today,expected",
    [
        (date(2026, 10, 19), date(2026, 11, 5)),
        (date(2026, 10, 20), date(2026, 11, 20)),
        (date(2026, 11, 4), date(2026, 11, 20)),
        (date(2026, 11, 5), date(2026, 12, 5)),
    ],
)
def test_default_horizon_is_the_payday_after_next(today, expected) -> None:
    assert default_horizon(today) == expected


def test_received_deposits_are_not_expected_again() -> None:
    credits = [
        Credit(date(2026, 10, 5), Decimal("1136548")),
        Credit(date(2026, 10, 8), Decimal("1050905")),
    ]
    out = expected_incomes(SOURCES, credits, date(2026, 10, 9), date(2026, 11, 5))
    assert [(i.on, i.amount) for i in out] == [
        (date(2026, 10, 20), Decimal("1136548")),
        (date(2026, 11, 5), Decimal("1136548")),
    ]


def test_weekend_payday_arrives_on_friday_and_counts_as_received() -> None:
    # 20-Sep-2026 was a Sunday; the payroll landed Friday the 18th.
    credits = [Credit(date(2026, 9, 18), Decimal("1136548"))]
    out = expected_incomes([Q20], credits, date(2026, 9, 19), date(2026, 10, 5))
    assert out == []


def test_bonus_does_not_pass_for_the_payroll() -> None:
    """Only the bonus arrived: the payroll (7.5% bigger) is still expected
    and shows up as late, instead of being confirmed by the bonus."""
    credits = [Credit(date(2026, 10, 8), Decimal("1050905"))]
    out = expected_incomes([Q5, BONUS], credits, date(2026, 10, 9), date(2026, 10, 19))
    assert [(i.name, i.on) for i in out] == [("Quincena 5 (5/10)", date(2026, 10, 5))]


def test_small_unrelated_credit_does_not_confirm_payroll() -> None:
    credits = [Credit(date(2026, 10, 20), Decimal("85000"))]
    out = expected_incomes([Q20], credits, date(2026, 10, 20), date(2026, 11, 4))
    assert [i.on for i in out] == [date(2026, 10, 20)]


def _pp(name, amount, due_day, paid_month=None):
    return SimpleNamespace(
        name=name, amount=Decimal(amount), due_day=due_day, paid_month=paid_month
    )


def test_planned_payments_become_dated_obligations() -> None:
    out = planned_obligations(
        [_pp("Arriendo", "850000", 24), _pp("Internet", "46500", 5)],
        today=date(2026, 10, 19),
        horizon_end=date(2026, 11, 5),
    )
    assert [(o.name, o.due, o.paid) for o in out] == [
        ("Arriendo (24/10)", date(2026, 10, 24), 0),
        # 5-Oct passed unchecked → still owed (overdue); 5-Nov is in range.
        ("Internet (5/10)", date(2026, 10, 5), 0),
        ("Internet (5/11)", date(2026, 11, 5), 0),
    ]


def test_checked_off_month_is_paid_and_past_paid_ones_disappear() -> None:
    out = planned_obligations(
        [_pp("Internet", "46500", 5, paid_month="2026-10")],
        today=date(2026, 10, 19),
        horizon_end=date(2026, 11, 5),
    )
    assert [o.due for o in out] == [date(2026, 11, 5)]


def test_planned_payment_without_day_uses_the_month_check() -> None:
    (unpaid,) = planned_obligations(
        [_pp("Movistar", "30000", None)], date(2026, 10, 19), date(2026, 11, 5)
    )
    assert (unpaid.due, unpaid.paid) == (None, 0)
    (paid,) = planned_obligations(
        [_pp("Movistar", "30000", None, "2026-10")], date(2026, 10, 19), date(2026, 11, 5)
    )
    assert paid.paid == Decimal("30000")


def _debt(minimum, due):
    return SimpleNamespace(
        id=uuid.uuid4(),
        bank_name="RappiCard",
        minimum_payment=None if minimum is None else Decimal(minimum),
        payment_due_date=due,
    )


def test_statement_minimum_minus_payments_made_against_it() -> None:
    debt = _debt("402708.83", date(2026, 10, 20))
    payments = [
        DebtPayment(debt.id, date(2026, 9, 11), Decimal("92392")),  # last statement
        DebtPayment(debt.id, date(2026, 10, 19), Decimal("200000")),  # partial, this one
        DebtPayment(uuid.uuid4(), date(2026, 10, 19), Decimal("999")),  # other card
    ]
    (ob,) = debt_obligations([debt], payments, date(2026, 10, 19))
    assert (ob.name, ob.due, ob.amount, ob.paid) == (
        "Mínimo RappiCard",
        date(2026, 10, 20),
        Decimal("402708.83"),
        Decimal("200000"),
    )


def test_old_statement_and_debts_without_minimum_are_skipped() -> None:
    debts = [_debt("92392", date(2026, 9, 20)), _debt(None, None)]
    assert debt_obligations(debts, [], date(2026, 10, 19)) == []


def test_minimum_without_due_date_is_kept_undated() -> None:
    (ob,) = debt_obligations([_debt("182224", None)], [], date(2026, 10, 19))
    assert ob.due is None


def test_debt_due_date_can_be_typed_for_cards_without_statement_email() -> None:
    from app.schemas.debt import DebtCreate, DebtUpdate

    created = DebtCreate(
        bank_name="Banco de Bogotá",
        total_amount="2513185",
        minimum_payment="182224",
        payment_due_date="2026-11-05",
    )
    assert created.payment_due_date == date(2026, 11, 5)
    assert DebtUpdate(payment_due_date=None).model_fields_set == {"payment_due_date"}
