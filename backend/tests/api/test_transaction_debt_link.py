"""PATCH /transactions/{id} with debt_id: point a debit at the manual debt it paid."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

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
    """First SELECT returns the transaction; later ones look debts up by the
    id bound in the WHERE clause."""

    def __init__(self, tx, debts):
        self.tx = tx
        self.debts = {d.id: d for d in debts}
        self.calls = 0
        self.committed = False

    async def execute(self, stmt):
        self.calls += 1
        if self.calls == 1:
            return _Result(self.tx)
        params = stmt.compile().params
        ids = [v for v in params.values() if isinstance(v, uuid.UUID)]
        return _Result(next((self.debts[i] for i in ids if i in self.debts), None))

    async def commit(self):
        self.committed = True

    async def refresh(self, _obj):
        return None


def _tx(**over):
    base = dict(
        id=uuid.uuid4(), amount=Decimal("100000"), merchant="Transferencia llave",
        category=None, transaction_type=TransactionType.debit, currency="COP",
        card_last_digits=None, occurred_at=datetime(2026, 11, 7, 20, tzinfo=timezone.utc),
        note=None, debt_id=None, source="davivienda", shared_amount=None,
    )
    base.update(over)
    return SimpleNamespace(**base)


def _debt(total="500000", email_sender=None):
    return SimpleNamespace(
        id=uuid.uuid4(), total_amount=Decimal(total), email_sender=email_sender
    )


def _client(tx, *debts):
    session = _FakeSession(tx, debts)
    app = FastAPI()
    app.include_router(transactions.router)
    app.dependency_overrides[deps.get_current_user] = lambda: SimpleNamespace(id=uuid.uuid4())
    app.dependency_overrides[deps.get_db] = lambda: session
    return TestClient(app), session


def test_linking_lowers_the_manual_debt_and_marks_it_a_debt_payment() -> None:
    mom = _debt("500000")
    tx = _tx()
    client, session = _client(tx, mom)
    resp = client.patch(f"/transactions/{tx.id}", json={"debt_id": str(mom.id)})
    assert resp.status_code == 200
    assert resp.json()["debt_id"] == str(mom.id)
    assert resp.json()["category"] == "debt_payment"
    assert mom.total_amount == Decimal("400000")
    assert session.committed


def test_moving_the_link_gives_the_amount_back_to_the_old_debt() -> None:
    mom, bank = _debt("400000"), _debt("2000000")
    tx = _tx(debt_id=mom.id, category="debt_payment")
    client, _ = _client(tx, mom, bank)
    resp = client.patch(f"/transactions/{tx.id}", json={"debt_id": str(bank.id)})
    assert resp.status_code == 200
    assert mom.total_amount == Decimal("500000")
    assert bank.total_amount == Decimal("1900000")


def test_unlinking_restores_the_balance() -> None:
    mom = _debt("400000")
    tx = _tx(debt_id=mom.id, category="debt_payment")
    client, _ = _client(tx, mom)
    resp = client.patch(f"/transactions/{tx.id}", json={"debt_id": None})
    assert resp.status_code == 200
    assert resp.json()["debt_id"] is None
    assert mom.total_amount == Decimal("500000")


def test_balance_never_goes_negative() -> None:
    mom = _debt("30000")
    tx = _tx()
    client, _ = _client(tx, mom)
    assert client.patch(f"/transactions/{tx.id}", json={"debt_id": str(mom.id)}).status_code == 200
    assert mom.total_amount == Decimal("0")


def test_email_linked_card_is_refused_as_target() -> None:
    card = _debt("915066", email_sender="rappi@example.com")
    tx = _tx()
    client, _ = _client(tx, card)
    resp = client.patch(f"/transactions/{tx.id}", json={"debt_id": str(card.id)})
    assert resp.status_code == 422
    assert card.total_amount == Decimal("915066")


def test_card_purchase_link_cannot_be_moved() -> None:
    card, mom = _debt("915066", email_sender="rappi@example.com"), _debt()
    tx = _tx(source="card", debt_id=card.id)
    client, _ = _client(tx, card, mom)
    resp = client.patch(f"/transactions/{tx.id}", json={"debt_id": str(mom.id)})
    assert resp.status_code == 409
    assert mom.total_amount == Decimal("500000")


def test_credit_cannot_pay_a_debt() -> None:
    mom = _debt()
    tx = _tx(transaction_type=TransactionType.credit)
    client, _ = _client(tx, mom)
    resp = client.patch(f"/transactions/{tx.id}", json={"debt_id": str(mom.id)})
    assert resp.status_code == 422


def test_unknown_debt_is_404() -> None:
    tx = _tx()
    client, _ = _client(tx)
    resp = client.patch(f"/transactions/{tx.id}", json={"debt_id": str(uuid.uuid4())})
    assert resp.status_code == 404
