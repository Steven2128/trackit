from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import deps
from app.api.routes import transactions
from app.models.transaction import TransactionType


class _Result:
    def __init__(self, row):
        self._row = row

    def scalar_one_or_none(self):
        return self._row


class _FakeSession:
    """Just enough AsyncSession for the PATCH route: one SELECT, commit, refresh."""

    def __init__(self, row):
        self.row = row
        self.committed = False

    async def execute(self, _stmt):
        return _Result(self.row)

    async def commit(self):
        self.committed = True

    async def refresh(self, _obj):
        return None


def _tx(source: str | None):
    return SimpleNamespace(
        id=uuid.uuid4(), amount=Decimal("1"), merchant="Desayuno", category="food",
        transaction_type=TransactionType.debit, currency="COP", card_last_digits=None,
        occurred_at="2026-10-15T21:21:00+00:00", note=None, debt_id=None, source=source,
    )


def _client(row) -> tuple[TestClient, _FakeSession]:
    session = _FakeSession(row)
    app = FastAPI()
    app.include_router(transactions.router)
    app.dependency_overrides[deps.get_current_user] = lambda: SimpleNamespace(id=uuid.uuid4())
    app.dependency_overrides[deps.get_db] = lambda: session
    return TestClient(app), session


def test_cash_expense_amount_can_be_edited() -> None:
    row = _tx("cash")
    client, session = _client(row)
    resp = client.patch(f"/transactions/{row.id}", json={"amount": "15700"})
    assert resp.status_code == 200
    assert Decimal(resp.json()["amount"]) == Decimal("15700")
    assert session.committed


@pytest.mark.parametrize("source", ["davivienda", "nequi", None])
def test_bank_transaction_amount_is_rejected(source) -> None:
    row = _tx(source)
    client, session = _client(row)
    resp = client.patch(f"/transactions/{row.id}", json={"amount": "15700"})
    assert resp.status_code == 409
    assert resp.json()["detail"] == "amount_not_editable"
    assert row.amount == Decimal("1")
    assert not session.committed
