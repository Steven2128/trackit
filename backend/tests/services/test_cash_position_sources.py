"""Stored rows → cash_position inputs. Income amounts mirror the user's real
deposit pattern (two quincenas + a separate bonus); the rest is fictitious."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services.cash_position import PositionStatus, compute_position
from app.services.cash_position_sources import (
    CardPurchase,
    Credit,
    DebtPayment,
    PaymentRecord,
    build_inputs,
    debt_obligations,
    default_horizon,
    expected_incomes,
    is_due_month,
    planned_obligations,
)
from app.services.cash_position import AmountStatus

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


def _pp(name, amount, due_day, paid_month=None, due_date=None):
    return SimpleNamespace(
        id=uuid.uuid4(),
        name=name,
        amount=Decimal(amount),
        due_day=due_day,
        due_date=due_date,
        paid_month=paid_month,
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


def _debt(minimum, due, *, planned=None, email_format="rappicard", bank="RappiCard"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        bank_name=bank,
        minimum_payment=None if minimum is None else Decimal(minimum),
        planned_payment=None if planned is None else Decimal(planned),
        payment_due_date=due,
        email_format=email_format,
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


def test_payment_on_the_previous_due_date_belongs_to_the_previous_statement() -> None:
    # Paid October's minimum on its due date; November's is still owed in full.
    debt = _debt("757430.83", date(2026, 11, 20))
    payments = [DebtPayment(debt.id, date(2026, 10, 20), Decimal("402708.83"))]
    (ob,) = debt_obligations([debt], payments, date(2026, 11, 12), date(2026, 12, 4))
    assert (ob.amount, ob.paid) == (Decimal("757430.83"), Decimal("0"))


def test_payment_before_the_statement_was_issued_does_not_count() -> None:
    # Late payment of the previous statement (21-Oct), before this one came.
    debt = _debt("757430.83", date(2026, 11, 20))
    debt.statement_at = datetime(2026, 11, 11, 5, tzinfo=timezone.utc)
    payments = [
        DebtPayment(debt.id, date(2026, 10, 21), Decimal("100000")),
        DebtPayment(debt.id, date(2026, 11, 15), Decimal("300000")),
    ]
    (ob,) = debt_obligations([debt], payments, date(2026, 11, 16), date(2026, 12, 4))
    assert ob.paid == Decimal("300000")


def test_next_statement_is_one_estimated_payment_from_purchases_since_the_cut() -> None:
    debt = _debt("757430.83", date(2026, 11, 20))
    debt.statement_at = datetime(2026, 11, 11, 5, tzinfo=timezone.utc)
    debt.next_installments = Decimal("69358.84")
    purchases = [
        CardPurchase(debt.id, datetime(2026, 10, 30, 18, tzinfo=timezone.utc), Decimal("10000")),
        CardPurchase(debt.id, datetime(2026, 11, 12, 18, tzinfo=timezone.utc), Decimal("25000")),
        CardPurchase(debt.id, datetime(2026, 11, 14, 1, tzinfo=timezone.utc), Decimal("15000")),
        CardPurchase(uuid.uuid4(), datetime(2026, 11, 14, 1, tzinfo=timezone.utc), Decimal("999")),
    ]
    obs = debt_obligations(
        [debt], [], date(2026, 11, 14), date(2026, 12, 20), purchases=purchases
    )
    assert [(o.name, o.due, o.amount, o.status) for o in obs] == [
        ("Próximo extracto RappiCard", date(2026, 12, 20), Decimal("109358.84"),
         AmountStatus.estimated),
        ("Mínimo RappiCard", date(2026, 11, 20), Decimal("757430.83"), AmountStatus.confirmed),
    ]
    # Past this statement's date and the next one hasn't arrived: only the estimate.
    (only,) = debt_obligations(
        [debt], [], date(2026, 11, 25), date(2026, 12, 20), purchases=purchases
    )
    assert only.due == date(2026, 12, 20)
    # Beyond the horizon, or nothing bought and no installments: nothing.
    assert len(debt_obligations([debt], [], date(2026, 11, 14), date(2026, 12, 4),
                                purchases=purchases)) == 1
    debt.next_installments = None
    assert len(debt_obligations([debt], [], date(2026, 11, 14), date(2026, 12, 20))) == 1


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


# --- Stage 3: one-offs, partial payments, planned debt payment, holds ---


def test_one_off_obligation_is_due_once() -> None:
    friend = _pp("Deuda amigo", "135000", None, due_date=date(2026, 11, 1))
    (ob,) = planned_obligations([friend], date(2026, 10, 19), date(2026, 11, 5))
    assert (ob.name, ob.due, ob.amount) == ("Deuda amigo", date(2026, 11, 1), Decimal("135000"))
    # Past the horizon: not yet. Checked off: gone.
    assert planned_obligations([friend], date(2026, 10, 19), date(2026, 10, 31)) == []
    paid = _pp("Deuda amigo", "135000", None, paid_month="2026-10", due_date=date(2026, 11, 1))
    (done,) = planned_obligations([paid], date(2026, 10, 19), date(2026, 11, 5))
    assert done.paid == done.amount  # still on the plan, as done
    # Once its date passed, a settled one-off leaves the plan.
    assert planned_obligations([paid], date(2026, 11, 2), date(2026, 11, 20)) == []


def test_partial_payments_add_up_per_due_date() -> None:
    rent = _pp("Arriendo", "850000", 24)
    records = [
        PaymentRecord(date(2026, 10, 24), Decimal("550000"), planned_payment_id=rent.id),
        PaymentRecord(date(2026, 10, 24), Decimal("100000"), planned_payment_id=rent.id),
        # Paying ahead belongs to November's due date, not October's.
        PaymentRecord(date(2026, 11, 24), Decimal("200000"), planned_payment_id=rent.id),
    ]
    obs = planned_obligations([rent], date(2026, 10, 19), date(2026, 11, 30), records)
    assert [(o.due, o.paid) for o in obs] == [
        (date(2026, 10, 24), Decimal("650000")),
        (date(2026, 11, 24), Decimal("200000")),
    ]
    assert obs[0].ref == f"planned:{rent.id}:2026-10-24"


def test_planned_debt_payment_replaces_the_minimum() -> None:
    bdb = _debt("182224", date(2026, 11, 5), planned="700000", email_format=None,
                bank="Banco de Bogotá")
    (ob,) = debt_obligations([bdb], [], date(2026, 10, 19), date(2026, 11, 5))
    assert (ob.name, ob.amount, ob.due) == ("Abono Banco de Bogotá", Decimal("700000"),
                                           date(2026, 11, 5))


def test_minimum_wins_when_planned_is_lower() -> None:
    debt = _debt("182224", date(2026, 11, 5), planned="100000")
    (ob,) = debt_obligations([debt], [], date(2026, 10, 19), date(2026, 11, 5))
    assert (ob.name, ob.amount) == ("Mínimo RappiCard", Decimal("182224"))


def test_hand_typed_debt_repeats_monthly_and_rolls_past_dates() -> None:
    bdb = _debt("182224", date(2026, 11, 5), planned="700000", email_format=None,
                bank="Banco de Bogotá")
    # 20-Nov: the 5-Nov date passed → next is 5-Dec (estimated); horizon 20-Dec.
    obs = debt_obligations([bdb], [], date(2026, 11, 20), date(2026, 12, 20))
    assert [(o.due, o.status.value) for o in obs] == [(date(2026, 12, 5), "estimated")]
    # Long horizon from today: 5-Nov (confirmed) and 5-Dec (estimated).
    obs = debt_obligations([bdb], [], date(2026, 10, 19), date(2026, 12, 5))
    assert [(o.due, o.status.value) for o in obs] == [
        (date(2026, 11, 5), "confirmed"),
        (date(2026, 12, 5), "estimated"),
    ]


def test_recorded_debt_payment_wins_over_email_receipts() -> None:
    debt = _debt("402708.83", date(2026, 10, 20))
    records = [PaymentRecord(date(2026, 10, 20), Decimal("402708.83"), debt_id=debt.id)]
    receipts = [DebtPayment(debt.id, date(2026, 10, 20), Decimal("402708.83"))]
    (ob,) = debt_obligations([debt], receipts, date(2026, 10, 19), date(2026, 11, 5), records)
    assert ob.paid == Decimal("402708.83")  # not counted twice


def test_users_fortnight_end_to_end() -> None:
    """The user's 19-Oct plan as stored rows (figures they reported; incomes
    estimated): brother's 550 held, Rappi minimum and Movistar tomorrow,
    rent, friend and grandparents before the 5th; internet and the 700
    Banco de Bogotá payment on the 5th, paid with the 5th payroll."""
    rent = _pp("Arriendo", "850000", 24)
    inputs = build_inputs(
        today=date(2026, 10, 19),
        horizon_end=date(2026, 11, 5),
        balance=Decimal("1125000"),
        income_sources=[Q5, BONUS, Q20],
        credits=[],
        planned_payments=[
            rent,
            _pp("Movistar", "30000", 20),
            _pp("Internet", "46500", 5, paid_month="2026-10"),
            _pp("Amigo", "135000", None, due_date=date(2026, 10, 25)),
            _pp("Abuelos", "100000", None, due_date=date(2026, 10, 25)),
        ],
        debts=[
            _debt("402708.83", date(2026, 10, 20)),
            _debt("182224", date(2026, 11, 5), planned="700000", email_format=None,
                  bank="Banco de Bogotá"),
        ],
        debt_payments=[],
        pay_due_on_payday=True,
        fund_holds=[SimpleNamespace(name="Hermano (arriendo)", amount=Decimal("550000"))],
    )
    pos = compute_position(inputs)
    assert pos.own == Decimal("575000")
    # 575.000 + 1.136.548 − 402.708,83 − 30.000 − 850.000 − 135.000 − 100.000
    assert pos.windows[1].balance_after == Decimal("193839.17")
    assert pos.free == Decimal("193839.17")
    assert pos.status is PositionStatus.provisional  # incomes are estimates


# --- bills every N months, variable amounts ---


@pytest.mark.parametrize(
    ("first_month", "year", "month", "due"),
    [
        ("2026-11", 2026, 11, True),
        ("2026-11", 2026, 12, False),
        ("2026-11", 2027, 1, True),
        ("2026-11", 2027, 2, False),
        ("2026-12", 2026, 10, True),  # parity holds backwards too
        ("2026-12", 2026, 11, False),
    ],
)
def test_every_two_months(first_month, year, month, due) -> None:
    p = SimpleNamespace(every_months=2, first_month=first_month)
    assert is_due_month(p, year, month) is due


def test_monthly_and_old_rows_are_always_due() -> None:
    assert is_due_month(SimpleNamespace(every_months=1, first_month=None), 2026, 12)
    assert is_due_month(SimpleNamespace(), 2026, 12)


def test_anchor_defaults_to_the_creation_month() -> None:
    from datetime import datetime, timezone

    p = SimpleNamespace(
        every_months=2, first_month=None, created_at=datetime(2026, 11, 7, tzinfo=timezone.utc)
    )
    assert is_due_month(p, 2027, 1) and not is_due_month(p, 2026, 12)


def test_water_skips_its_off_month_and_utilities_are_estimates() -> None:
    water = _pp("Agua", "105930", 7)
    water.every_months, water.first_month, water.amount_varies = 2, "2026-11", True
    power = _pp("Luz", "97850", 7)
    power.every_months, power.first_month, power.amount_varies = 1, None, True
    rent = _pp("Arriendo", "850000", 24)

    out = planned_obligations(
        [water, power, rent], today=date(2026, 11, 20), horizon_end=date(2027, 1, 20)
    )
    by_name = {o.name: o for o in out}

    assert "Agua (7/12)" not in by_name
    assert "Agua (7/1)" in by_name
    assert {"Luz (7/12)", "Luz (7/1)"} <= set(by_name)
    assert by_name["Luz (7/12)"].status == AmountStatus.estimated
    assert by_name["Arriendo (24/11)"].status == AmountStatus.confirmed


# --- income paid early ---

EARLY_BONUS = SimpleNamespace(
    name="Bonificación", amount=Decimal("1050905"), expected_day=8, early_from_day=21
)


def test_bonus_paid_on_the_30th_counts_for_next_month() -> None:
    """The real case: November's bonus landed on 30-Oct."""
    credits = [Credit(date(2026, 10, 30), Decimal("1050905"))]
    out = expected_incomes([EARLY_BONUS], credits, date(2026, 11, 7), date(2026, 12, 5))
    assert out == []


def test_without_early_window_the_30th_is_too_soon() -> None:
    credits = [Credit(date(2026, 10, 30), Decimal("1050905"))]
    out = expected_incomes([BONUS], credits, date(2026, 11, 7), date(2026, 12, 5))
    assert [i.name for i in out] == ["Bonificación (6/11)"]


def test_early_window_starts_on_its_day() -> None:
    credits = [Credit(date(2026, 10, 20), Decimal("1050905"))]  # the day before the 21st
    out = expected_incomes([EARLY_BONUS], credits, date(2026, 11, 7), date(2026, 12, 5))
    assert [i.name for i in out] == ["Bonificación (6/11)"]
