from decimal import Decimal
from types import SimpleNamespace

from app.models.transaction import TransactionType
from app.services.contact_balance import balance_effect

D, C = TransactionType.debit, TransactionType.credit


def _row(amount, type_, *, category=None, shared=None, source="davivienda"):
    return SimpleNamespace(
        amount=Decimal(amount), transaction_type=type_, category=category,
        shared_amount=Decimal(shared) if shared is not None else None, source=source,
    )


def test_bill_the_user_paid_half_theirs() -> None:
    assert balance_effect(_row("97850", D, category="bills", shared="48925")) == Decimal("48925")


def test_expense_the_contact_paid_user_owes_own_part() -> None:
    row = _row("60000", D, category="food", shared="30000", source="contact")
    assert balance_effect(row) == Decimal("-30000")


def test_contact_paid_something_all_the_users() -> None:
    assert balance_effect(_row("20000", D, shared="0", source="contact")) == Decimal("-20000")


def test_payback_from_the_contact_lowers_what_they_owe() -> None:
    assert balance_effect(_row("40000", C, category="reimbursement")) == Decimal("-40000")


def test_user_paying_back_or_lending_raises_it() -> None:
    assert balance_effect(_row("100000", D, category="reimbursement")) == Decimal("100000")


def test_plain_movements_dont_count() -> None:
    assert balance_effect(_row("50000", D, category="food")) == 0
    assert balance_effect(_row("50000", C)) == 0


def test_loan_and_payback_settle_to_zero() -> None:
    lent = _row("100000", D, shared="100000")
    back = _row("100000", C, category="reimbursement")
    assert balance_effect(lent) + balance_effect(back) == 0
