from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.services.cards import add_month, installment_plans, statement_totals


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
