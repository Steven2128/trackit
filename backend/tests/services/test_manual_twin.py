"""A bank email for a movement the user already typed in backs that row."""
import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

from app.models.transaction import TransactionType
from app.services.email_sync import find_manual_twin

WHEN = datetime(2026, 11, 3, 15, tzinfo=timezone.utc)


class _Db:
    def __init__(self, rows):
        self.rows = rows
        self.queries = 0

    async def execute(self, _stmt):
        self.queries += 1
        rows = self.rows
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: rows))


def _parsed():
    return SimpleNamespace(
        transaction_type=TransactionType.credit, amount=Decimal("40000"), occurred_at=WHEN
    )


def test_closest_typed_row_wins() -> None:
    far = SimpleNamespace(occurred_at=WHEN - timedelta(days=2))
    near = SimpleNamespace(occurred_at=WHEN + timedelta(hours=3))
    twin = asyncio.run(find_manual_twin(_Db([far, near]), "u", "davivienda", _parsed()))
    assert twin is near


def test_no_typed_row_means_a_new_one() -> None:
    assert asyncio.run(find_manual_twin(_Db([]), "u", "nequi", _parsed())) is None


def test_only_bank_accounts_are_looked_up() -> None:
    db = _Db([SimpleNamespace(occurred_at=WHEN)])
    assert asyncio.run(find_manual_twin(db, "u", "card", _parsed())) is None
    assert db.queries == 0
