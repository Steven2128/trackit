from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from app.models.transaction import TransactionType
from app.services.statement_reconciler import (
    StatementRow,
    category_for,
    match_statement_rows,
)

D1 = date(2026, 6, 1)
D2 = date(2026, 6, 2)


def _row(index: int, local_date: date, amount: str, tx_type: TransactionType) -> StatementRow:
    return StatementRow(
        index=index, local_date=local_date, description="X", amount=Decimal(amount), tx_type=tx_type
    )


class TestMatchStatementRows:
    def test_exact_match_leaves_nothing_missing(self) -> None:
        rows = [_row(0, D1, "50000", TransactionType.debit)]
        db_rows = [(D1, Decimal("50000"), TransactionType.debit)]

        matched, missing = match_statement_rows(rows, db_rows)

        assert matched == 1
        assert missing == []

    def test_unmatched_row_is_missing(self) -> None:
        rows = [_row(0, D1, "4.77", TransactionType.credit)]

        matched, missing = match_statement_rows(rows, [])

        assert matched == 0
        assert missing == rows

    def test_off_by_one_day_still_matches(self) -> None:
        rows = [_row(0, D2, "10000", TransactionType.debit)]
        db_rows = [(D1, Decimal("10000"), TransactionType.debit)]

        matched, missing = match_statement_rows(rows, db_rows)

        assert matched == 1
        assert missing == []

    def test_two_days_off_does_not_match(self) -> None:
        rows = [_row(0, D1 + timedelta(days=2), "10000", TransactionType.debit)]
        db_rows = [(D1, Decimal("10000"), TransactionType.debit)]

        matched, missing = match_statement_rows(rows, db_rows)

        assert matched == 0
        assert missing == rows

    def test_same_day_same_amount_matched_by_count(self) -> None:
        """Statement has no timestamps — two identical rows match two DB rows,
        a third identical row (no more DB rows) is reported missing."""
        rows = [_row(i, D1, "20000", TransactionType.debit) for i in range(3)]
        db_rows = [(D1, Decimal("20000"), TransactionType.debit)] * 2

        matched, missing = match_statement_rows(rows, db_rows)

        assert matched == 2
        assert len(missing) == 1

    def test_type_mismatch_does_not_match(self) -> None:
        rows = [_row(0, D1, "20000", TransactionType.debit)]
        db_rows = [(D1, Decimal("20000"), TransactionType.credit)]

        matched, missing = match_statement_rows(rows, db_rows)

        assert matched == 0
        assert missing == rows


class TestCategoryFor:
    def test_retiro_prefix_is_cash_withdrawal(self) -> None:
        assert category_for("RETIRO 0010212462_Aeropuerto J 00 Se") == "cash_withdrawal"

    def test_pago_tarjeta_is_transfer(self) -> None:
        assert category_for("Pago tarjeta canal electronico") == "transfer"

    def test_unmatched_description_falls_back_to_categorizer(self) -> None:
        assert category_for("COMPRA RAPPI COLOMBIA*DL A") is not None
