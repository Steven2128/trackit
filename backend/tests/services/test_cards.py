from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.services.cards import (
    add_month,
    current_card_payment,
    installment_plans,
    statement_totals,
)


def _line(on, description, amount, billed=None, n=None, of=None, pending=None):
    return SimpleNamespace(
        posted_on=on,
        description=description,
        amount=Decimal(amount),
        billed=None if billed is None else Decimal(billed),
        installment=n,
        installments=of,
        pending=None if pending is None else Decimal(pending),
    )


LINES = [
    _line(date(2026, 9, 11), "MERCADO PAGO*MERCADOLI", "59800", "19933.33", 2, 3, "19933.34"),
    _line(date(2026, 9, 11), "MERCADO PAGO*MERCADOLI", "219703", "29425.50", 2, 6, "117702"),
    _line(date(2026, 8, 1), "VIEJA", "90000", "30000", 3, 3, "0"),
    _line(date(2026, 10, 9), "BERSHKA TESORO", "285700", "285700", 1, 1, "0"),
    _line(date(2026, 10, 20), "PAGOS RAPPIPAY APP", "-402708.83"),
]


def test_installment_plans_running_first_and_what_the_next_statement_bills() -> None:
    plans = installment_plans(LINES)
    assert [(p.description, p.installment, p.installments, p.remaining, p.next_amount) for p in plans] == [
        ("MERCADO PAGO*MERCADOLI", 2, 6, 4, Decimal("29425.50")),
        ("MERCADO PAGO*MERCADOLI", 2, 3, 1, Decimal("19933.34")),
        ("VIEJA", 3, 3, 0, Decimal("0")),  # finished: last, nothing more to bill
    ]


def test_statement_totals_split_purchases_of_the_period_and_payments() -> None:
    bought, paid = statement_totals(LINES, date(2026, 10, 9))
    assert (bought, paid) == (Decimal("285700"), Decimal("402708.83"))


def test_add_month_clamps_the_day() -> None:
    assert add_month(date(2026, 11, 10)) == date(2026, 12, 10)
    assert add_month(date(2026, 12, 20)) == date(2027, 1, 20)
    assert add_month(date(2027, 1, 31)) == date(2027, 2, 28)


def _payment(paid, purchases=(), installments=Decimal("69358.84"), balance=Decimal("387171.34")):
    return current_card_payment(
        statement_minimum=Decimal("757430.83"),
        statement_due=date(2026, 11, 20),
        cutoff=date(2026, 11, 10),
        paid_since_cutoff=Decimal(paid),
        purchases_since_cutoff=list(purchases),
        next_installments=installments,
        balance=balance,
    )


def test_current_payment_is_what_is_left_of_the_statement_minimum() -> None:
    p = _payment("400000", [(date(2026, 11, 13), Decimal("21400"))])
    assert p is not None
    assert (p.amount, p.due_date, p.accruing) == (Decimal("357430.83"), date(2026, 11, 20), False)


def test_once_paid_the_next_minimum_accrues_with_each_purchase() -> None:
    purchases = [(date(2026, 11, 13), Decimal("21400")), (date(2026, 11, 21), Decimal("139915"))]
    p = _payment("757430.83", purchases)
    assert p is not None
    assert p.accruing and p.due_date == date(2026, 12, 20)
    assert p.amount == Decimal("21400") + Decimal("139915") + Decimal("69358.84")


def test_accruing_minimum_skips_purchases_after_the_next_cutoff_and_caps_at_balance() -> None:
    p = _payment("757430.83", [(date(2026, 12, 11), Decimal("50000"))])
    assert p is not None and p.amount == Decimal("69358.84")
    capped = _payment("757430.83", [(date(2026, 11, 13), Decimal("90000"))], balance=Decimal("100000"))
    assert capped is not None and capped.amount == Decimal("100000")


def test_no_statement_no_current_payment() -> None:
    assert current_card_payment(
        statement_minimum=None, statement_due=None, cutoff=None,
        paid_since_cutoff=Decimal("0"), purchases_since_cutoff=[],
        next_installments=None, balance=Decimal("0"),
    ) is None
