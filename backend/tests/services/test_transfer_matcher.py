from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

from app.services.transfer_matcher import (
    DEBT_PAYMENT_TOLERANCE,
    DEBT_PAYMENT_WINDOW,
    PSE_WINDOW,
    apply_pse_receipt,
    pair_transfers,
)

BASE = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)


def _tx(amount: str, offset_minutes: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        amount=Decimal(amount),
        occurred_at=BASE + timedelta(minutes=offset_minutes),
    )


class TestPairTransfers:
    def test_exact_amount_within_window_pairs(self) -> None:
        debit = _tx("50000", 0)
        credit = _tx("50000", 3)

        pairs = pair_transfers([debit], [credit])

        assert pairs == [(debit.id, credit.id)]

    def test_amount_mismatch_does_not_pair(self) -> None:
        debit = _tx("50000", 0)
        credit = _tx("50001", 3)

        assert pair_transfers([debit], [credit]) == []

    def test_outside_time_window_does_not_pair(self) -> None:
        debit = _tx("50000", 0)
        credit = _tx("50000", 11)

        assert pair_transfers([debit], [credit]) == []

    def test_credit_slightly_before_debit_pairs(self) -> None:
        """Clock skew between banks: credit notification can land first."""
        debit = _tx("50000", 0)
        credit = _tx("50000", -5)

        pairs = pair_transfers([debit], [credit])

        assert pairs == [(debit.id, credit.id)]

    def test_credit_used_at_most_once(self) -> None:
        """Two identical debits, one credit — only one pair forms."""
        debit_a = _tx("20000", 0)
        debit_b = _tx("20000", 1)
        credit = _tx("20000", 2)

        pairs = pair_transfers([debit_a, debit_b], [credit])

        assert len(pairs) == 1
        # Earliest debit wins.
        assert pairs[0] == (debit_a.id, credit.id)

    def test_closest_credit_wins_for_a_debit(self) -> None:
        debit = _tx("30000", 0)
        credit_far = _tx("30000", 9)
        credit_near = _tx("30000", 1)

        pairs = pair_transfers([debit], [credit_far, credit_near])

        assert pairs == [(debit.id, credit_near.id)]

    def test_multiple_independent_pairs(self) -> None:
        debit_a = _tx("10000", 0)
        debit_b = _tx("99999", 30)
        credit_a = _tx("10000", 2)
        credit_b = _tx("99999", 31)

        pairs = pair_transfers([debit_a, debit_b], [credit_a, credit_b])

        assert sorted(pairs) == sorted(
            [(debit_a.id, credit_a.id), (debit_b.id, credit_b.id)]
        )

    def test_empty_inputs(self) -> None:
        assert pair_transfers([], []) == []
        assert pair_transfers([_tx("100", 0)], []) == []
        assert pair_transfers([], [_tx("100", 0)]) == []


class TestDebtPaymentPairing:
    """Card receipt vs the bank debit that funded it (match_debt_payments)."""

    def _pair(self, debit: SimpleNamespace, receipt: SimpleNamespace) -> list:
        return pair_transfers(
            [debit], [receipt], window=DEBT_PAYMENT_WINDOW, tolerance=DEBT_PAYMENT_TOLERANCE
        )

    def test_cents_on_the_card_side_pair(self) -> None:
        """RappiCard bills 402.708,83; Davivienda debits 402.708."""
        debit = _tx("402708.00", 0)
        receipt = _tx("402708.83", 65)

        assert self._pair(debit, receipt) == [(debit.id, receipt.id)]

    def test_a_peso_apart_does_not_pair(self) -> None:
        assert self._pair(_tx("402708", 0), _tx("402709", 5)) == []

    def test_late_email_within_two_hours_pairs(self) -> None:
        debit = _tx("150000", 0)
        receipt = _tx("150000", 119)

        assert self._pair(debit, receipt) == [(debit.id, receipt.id)]

    def test_beyond_two_hours_does_not_pair(self) -> None:
        assert self._pair(_tx("150000", 0), _tx("150000", 121)) == []


class TestApplyPseReceipt:
    """What the bank debit inherits from the PSE receipt it absorbs."""

    @staticmethod
    def _row(merchant, category=None, note=None, pair=None) -> SimpleNamespace:
        return SimpleNamespace(
            merchant=merchant, category=category, note=note, transfer_pair_id=pair
        )

    def test_generic_pse_merchant_takes_the_biller(self) -> None:
        bank = self._row("PSE 101 FINTECH S.A.S.")
        apply_pse_receipt(self._row("Vanti S.A. ESP", "utilities", "gas oct"), bank)

        assert (bank.merchant, bank.category, bank.note) == (
            "Vanti S.A. ESP",
            "utilities",
            "gas oct",
        )

    def test_bank_data_wins_when_present(self) -> None:
        bank = self._row("COMCEL PAGO DE FACTURA", "utilities", "mine")
        apply_pse_receipt(self._row("Claro", "phone", "theirs"), bank)

        assert (bank.merchant, bank.category, bank.note) == (
            "COMCEL PAGO DE FACTURA",
            "utilities",
            "mine",
        )

    def test_card_payment_pairing_moves_to_the_bank_debit(self) -> None:
        pair = uuid.uuid4()
        bank = self._row("PSE Banco de Bogota")
        apply_pse_receipt(self._row("Banco de Bogota", "debt_payment", pair=pair), bank)

        assert (bank.category, bank.transfer_pair_id) == ("debt_payment", pair)


def test_pse_receipt_pairs_with_late_bank_debit_in_whole_pesos() -> None:
    """Receipt timestamped at email arrival; bank debit minutes earlier."""
    receipt = _tx("16520", 0)
    bank = _tx("16520", -40)
    other = _tx("16520", -200)

    assert pair_transfers(
        [receipt], [other, bank], window=PSE_WINDOW, tolerance=DEBT_PAYMENT_TOLERANCE
    ) == [(receipt.id, bank.id)]
