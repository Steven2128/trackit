from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

from app.services.transfer_matcher import pair_transfers

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
