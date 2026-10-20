from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import deps
from app.api.routes import plan
from app.models.obligation_payment import ObligationPayment
from app.models.transaction import Transaction


class _Result:
    def __init__(self, row):
        self._row = row

    def scalar_one_or_none(self):
        return self._row


class _FakeSession:
    """Answers each SELECT with the next queued row."""

    def __init__(self, *rows):
        self._rows = list(rows)
        self.added = []
        self.deleted = []
        self.committed = False

    async def execute(self, _stmt):
        return _Result(self._rows.pop(0))

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()

    async def delete(self, obj):
        self.deleted.append(obj)

    async def commit(self):
        self.committed = True

    async def refresh(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        if getattr(obj, "created_at", None) is None:
            obj.created_at = "2026-10-20T12:00:00+00:00"


@pytest.fixture(autouse=True)
def reconcile_calls(monkeypatch):
    calls = []

    async def _record(_db, _user_id, before, after):
        calls.append((before, after))

    monkeypatch.setattr(plan, "keep_cash_reconciled", _record)
    return calls


def _client(session) -> TestClient:
    app = FastAPI()
    app.include_router(plan.router)
    app.dependency_overrides[deps.get_current_user] = lambda: SimpleNamespace(id=uuid.uuid4())
    app.dependency_overrides[deps.get_db] = lambda: session
    return TestClient(app)


RENT = SimpleNamespace(id=uuid.uuid4(), name="Arriendo")
BDB = SimpleNamespace(id=uuid.uuid4(), bank_name="Banco de Bogotá")


def test_cash_payment_also_logs_the_cash_expense(reconcile_calls) -> None:
    session = _FakeSession(RENT)
    resp = _client(session).post(
        "/obligation-payments",
        json={
            "planned_payment_id": str(RENT.id),
            "due_date": "2026-10-24",
            "amount": "550000",
            "from_cash": True,
        },
    )
    assert resp.status_code == 201
    tx, record = session.added
    assert isinstance(tx, Transaction) and isinstance(record, ObligationPayment)
    assert (tx.source, tx.amount, tx.merchant, tx.category) == (
        "cash", Decimal("550000"), "Arriendo", None
    )
    assert record.transaction_id == tx.id
    assert record.due_date == date(2026, 10, 24)
    assert len(reconcile_calls) == 1  # backdated or not, the count is respected


def test_bank_payment_is_only_recorded(reconcile_calls) -> None:
    session = _FakeSession(BDB)
    resp = _client(session).post(
        "/obligation-payments",
        json={"debt_id": str(BDB.id), "due_date": "2026-11-05", "amount": "700000"},
    )
    assert resp.status_code == 201
    (record,) = session.added
    assert record.transaction_id is None
    assert reconcile_calls == []


def test_card_paid_in_cash_is_not_spending() -> None:
    session = _FakeSession(BDB)
    _client(session).post(
        "/obligation-payments",
        json={"debt_id": str(BDB.id), "due_date": "2026-11-05", "amount": "700000",
              "from_cash": True},
    )
    tx = session.added[0]
    assert (tx.merchant, tx.category) == ("Pago Banco de Bogotá", "debt_payment")


@pytest.mark.parametrize(
    "payload,detail",
    [
        ({"due_date": "2026-10-24", "amount": "1"}, "one_parent_required"),
        (
            {"planned_payment_id": str(uuid.uuid4()), "debt_id": str(uuid.uuid4()),
             "due_date": "2026-10-24", "amount": "1"},
            "one_parent_required",
        ),
    ],
)
def test_payment_needs_exactly_one_parent(payload, detail) -> None:
    session = _FakeSession()
    resp = _client(session).post("/obligation-payments", json=payload)
    assert resp.status_code == 422
    assert resp.json()["detail"] == detail
    assert not session.committed


def test_payment_in_the_future_is_rejected() -> None:
    tomorrow = (date.today() + timedelta(days=2)).isoformat()
    session = _FakeSession(RENT)
    resp = _client(session).post(
        "/obligation-payments",
        json={"planned_payment_id": str(RENT.id), "due_date": "2026-10-24",
              "amount": "1", "paid_on": tomorrow},
    )
    assert resp.status_code == 422
    assert not session.committed


def test_deleting_a_cash_payment_removes_its_expense(reconcile_calls) -> None:
    tx = SimpleNamespace(id=uuid.uuid4(), amount=Decimal("550000"), occurred_at="t")
    record = SimpleNamespace(id=uuid.uuid4(), transaction_id=tx.id)
    session = _FakeSession(record, tx)
    assert _client(session).delete(f"/obligation-payments/{record.id}").status_code == 204
    assert session.deleted == [tx, record]
    assert reconcile_calls == [((Decimal("550000"), "t"), None)]
