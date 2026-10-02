from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models.account import AccountKind
from app.models.transaction import TransactionType
from app.parsers.davivienda import DaviviendaParser
from app.services.net_worth import Movement, account_delta, computed_balance
from tests._helpers import load_eml_fixture

OPENING = datetime(2026, 10, 1, tzinfo=timezone.utc)
D, C = TransactionType.debit, TransactionType.credit


def _m(source, type_, amount, category=None, offset_hours=1) -> Movement:
    return Movement(
        source=source,
        transaction_type=type_,
        category=category,
        amount=Decimal(amount),
        occurred_at=OPENING + timedelta(hours=offset_hours),
    )


class TestAccountDelta:
    @pytest.mark.parametrize(
        ("kind", "movement", "expected"),
        [
            # Bank accounts: everything from their own source moves them.
            (AccountKind.davivienda, _m("davivienda", C, "1000000"), "1000000"),
            (AccountKind.davivienda, _m("davivienda", D, "50000"), "-50000"),
            (AccountKind.davivienda, _m("davivienda", D, "190000", "transfer"), "-190000"),
            (AccountKind.davivienda, _m("davivienda", D, "384000", "debt_payment"), "-384000"),
            (AccountKind.nequi, _m("nequi", C, "190000", "transfer"), "190000"),
            # Other sources don't touch them.
            (AccountKind.davivienda, _m("nequi", D, "50000"), "0"),
            (AccountKind.nequi, _m("card", D, "29400"), "0"),
            # Cash: withdrawals in, typed-in expenses out.
            (AccountKind.cash, _m("davivienda", D, "200000", "cash_withdrawal"), "200000"),
            (AccountKind.cash, _m("cash", D, "15000", "food"), "-15000"),
            (AccountKind.cash, _m("davivienda", D, "50000", "food"), "0"),
            (AccountKind.cash, _m("card", D, "29400"), "0"),
        ],
    )
    def test_delta(self, kind, movement, expected) -> None:
        assert account_delta(kind, movement) == Decimal(expected)


class TestComputedBalance:
    def test_transfer_between_own_accounts_keeps_total(self) -> None:
        moves = [
            _m("davivienda", D, "190000", "transfer"),
            _m("nequi", C, "190000", "transfer"),
        ]
        davi = computed_balance(AccountKind.davivienda, Decimal("500000"), OPENING, moves)
        nequi = computed_balance(AccountKind.nequi, Decimal("10000"), OPENING, moves)

        assert davi == Decimal("310000")
        assert nequi == Decimal("200000")
        assert davi + nequi == Decimal("510000")

    def test_movements_before_opening_are_already_in_the_opening_balance(self) -> None:
        old = _m("davivienda", D, "50000", offset_hours=-2)
        assert computed_balance(AccountKind.davivienda, Decimal("100"), OPENING, [old]) == 100

    def test_adjustments_are_added(self) -> None:
        moves = [_m("davivienda", D, "50000")]
        balance = computed_balance(
            AccountKind.davivienda, Decimal("100000"), OPENING, moves, Decimal("-5000")
        )
        assert balance == Decimal("45000")


def test_davivienda_retiro_is_cash_withdrawal() -> None:
    envelope = load_eml_fixture("davivienda/compra_establecimiento.eml")
    envelope = replace(
        envelope,
        html_body=envelope.html_body.replace(
            "Compra       en Establecimiento,", "Retiro en Cajero,"
        ),
    )
    tx = DaviviendaParser().parse(envelope)

    assert tx is not None
    assert tx.transaction_type == TransactionType.debit
    assert tx.category == "cash_withdrawal"
