from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
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
    """Just enough AsyncSession for the cash routes: one SELECT, add/delete,
    commit, refresh."""

    def __init__(self, row):
        self.row = row
        self.committed = False
        self.added = []
        self.deleted = []

    async def execute(self, _stmt):
        return _Result(self.row)

    def add(self, obj):
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def commit(self):
        self.committed = True

    async def refresh(self, obj):
        # What the DB would fill on insert.
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        return None


@pytest.fixture(autouse=True)
def reconcile_calls(monkeypatch):
    """Records keep_cash_reconciled calls (its math is tested in
    tests/services/test_net_worth.py) instead of querying accounts."""
    calls = []

    async def _record(_db, _user_id, before, after):
        calls.append((before, after))

    monkeypatch.setattr(transactions, "keep_cash_reconciled", _record)
    return calls


OCCURRED = datetime(2026, 10, 15, 21, 21, tzinfo=timezone.utc)


def _tx(source: str | None):
    return SimpleNamespace(
        id=uuid.uuid4(), amount=Decimal("1"), merchant="Desayuno", category="food",
        transaction_type=TransactionType.debit, currency="COP", card_last_digits=None,
        occurred_at=OCCURRED, note=None, debt_id=None, source=source,
        shared_amount=None,
    )


def _client(row) -> tuple[TestClient, _FakeSession]:
    session = _FakeSession(row)
    app = FastAPI()
    app.include_router(transactions.router)
    app.dependency_overrides[deps.get_current_user] = lambda: SimpleNamespace(id=uuid.uuid4())
    app.dependency_overrides[deps.get_db] = lambda: session
    return TestClient(app), session


def test_cash_expense_amount_can_be_edited(reconcile_calls) -> None:
    row = _tx("cash")
    client, session = _client(row)
    resp = client.patch(f"/transactions/{row.id}", json={"amount": "15700"})
    assert resp.status_code == 200
    assert Decimal(resp.json()["amount"]) == Decimal("15700")
    assert session.committed
    # The fix must not lower the cash the user already counted.
    assert reconcile_calls == [((Decimal("1"), OCCURRED), (Decimal("15700"), OCCURRED))]


def test_cash_expense_date_can_be_edited(reconcile_calls) -> None:
    row = _tx("cash")
    client, session = _client(row)
    yesterday = "2026-10-14T17:00:00+00:00"
    resp = client.patch(f"/transactions/{row.id}", json={"occurred_at": yesterday})
    assert resp.status_code == 200
    assert resp.json()["occurred_at"].startswith("2026-10-14T17:00:00")
    assert session.committed
    new_date = datetime(2026, 10, 14, 17, tzinfo=timezone.utc)
    assert reconcile_calls == [((Decimal("1"), OCCURRED), (Decimal("1"), new_date))]


def test_editing_only_the_name_leaves_reconciliation_alone(reconcile_calls) -> None:
    row = _tx("cash")
    client, _ = _client(row)
    assert client.patch(f"/transactions/{row.id}", json={"merchant": "Huevos"}).status_code == 200
    assert reconcile_calls == []


@pytest.mark.parametrize("source", ["davivienda", "nequi", None])
def test_bank_transaction_date_is_rejected(source, reconcile_calls) -> None:
    row = _tx(source)
    client, session = _client(row)
    resp = client.patch(
        f"/transactions/{row.id}", json={"occurred_at": "2026-10-14T17:00:00+00:00"}
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "date_not_editable"
    assert row.occurred_at == OCCURRED
    assert not session.committed
    assert reconcile_calls == []


@pytest.mark.parametrize(
    "value",
    [
        (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),  # future
        "2026-10-14T17:00:00",  # no timezone: ambiguous day
    ],
)
def test_invalid_expense_date_is_422(value) -> None:
    row = _tx("cash")
    client, session = _client(row)
    resp = client.patch(f"/transactions/{row.id}", json={"occurred_at": value})
    assert resp.status_code == 422
    assert not session.committed


def test_cash_expense_can_be_logged_on_a_past_day(reconcile_calls) -> None:
    client, session = _client(None)
    resp = client.post(
        "/transactions/cash",
        json={
            "amount": "12000",
            "merchant": "Helado",
            "category": "food",
            "occurred_at": "2026-10-18T17:00:00+00:00",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["occurred_at"].startswith("2026-10-18T17:00:00")
    (tx,) = session.added
    assert tx.source == "cash"
    assert reconcile_calls == [(None, (Decimal("12000"), tx.occurred_at))]


def test_cash_expense_in_the_future_is_422() -> None:
    client, session = _client(None)
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    resp = client.post(
        "/transactions/cash",
        json={"amount": "12000", "merchant": "Helado", "occurred_at": tomorrow},
    )
    assert resp.status_code == 422
    assert session.added == []


def test_deleting_a_cash_expense_keeps_the_count(reconcile_calls) -> None:
    row = _tx("cash")
    client, session = _client(row)
    assert client.delete(f"/transactions/{row.id}").status_code == 204
    assert session.deleted == [row]
    assert reconcile_calls == [((Decimal("1"), OCCURRED), None)]


@pytest.mark.parametrize("source", ["davivienda", "nequi", None])
def test_bank_transaction_amount_is_rejected(source) -> None:
    row = _tx(source)
    client, session = _client(row)
    resp = client.patch(f"/transactions/{row.id}", json={"amount": "15700"})
    assert resp.status_code == 409
    assert resp.json()["detail"] == "amount_not_editable"
    assert row.amount == Decimal("1")
    assert not session.committed


# --- shared expenses ---


def _bill(amount: str = "97850", type_=TransactionType.debit):
    row = _tx("davivienda")
    row.amount, row.transaction_type = Decimal(amount), type_
    return row


def test_bank_debit_can_be_shared() -> None:
    row = _bill()
    client, session = _client(row)
    resp = client.patch(f"/transactions/{row.id}", json={"shared_amount": "48925"})

    assert resp.status_code == 200
    assert row.shared_amount == Decimal("48925")
    assert Decimal(resp.json()["shared_amount"]) == Decimal("48925")
    assert session.committed


@pytest.mark.parametrize("value", ["0", None])
def test_zero_or_null_unshares(value) -> None:
    row = _bill()
    row.shared_amount = Decimal("48925")
    client, _ = _client(row)
    resp = client.patch(f"/transactions/{row.id}", json={"shared_amount": value})

    assert resp.status_code == 200
    assert row.shared_amount is None


def test_shared_part_cannot_exceed_the_amount() -> None:
    row = _bill()
    client, session = _client(row)
    resp = client.patch(f"/transactions/{row.id}", json={"shared_amount": "97851"})

    assert resp.status_code == 422
    assert resp.json()["detail"] == "shared_exceeds_amount"
    assert not session.committed


def test_credits_cannot_be_shared() -> None:
    row = _bill("48925", TransactionType.credit)
    client, _ = _client(row)
    resp = client.patch(f"/transactions/{row.id}", json={"shared_amount": "1000"})

    assert resp.status_code == 422
    assert resp.json()["detail"] == "shared_needs_debit"


def test_lowering_a_cash_amount_below_the_shared_part_is_rejected() -> None:
    row = _tx("cash")
    row.amount, row.shared_amount = Decimal("20000"), Decimal("10000")
    client, session = _client(row)
    resp = client.patch(f"/transactions/{row.id}", json={"amount": "5000"})

    assert resp.status_code == 422
    assert not session.committed


def test_reimbursement_is_an_allowed_category() -> None:
    row = _bill("48925", TransactionType.credit)
    client, _ = _client(row)
    resp = client.patch(f"/transactions/{row.id}", json={"category": "reimbursement"})

    assert resp.status_code == 200
    assert row.category == "reimbursement"
