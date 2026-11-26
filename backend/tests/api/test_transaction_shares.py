"""PATCH /transactions/{id} with ``shares``: one debit split among several
people. shared_amount becomes the sum so spending math is untouched."""

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
from app.models.transaction_share import TransactionShare
from app.services.contact_balance import balance_effects


class _Result:
    def __init__(self, row):
        self._row = row

    def scalar_one_or_none(self):
        return self._row


class _Session:
    """Every SELECT finds the row (the transaction, and "the contact is
    yours")."""

    def __init__(self, row):
        self.row = row
        self.committed = False

    async def execute(self, _stmt):
        return _Result(self.row)

    async def commit(self):
        self.committed = True

    async def refresh(self, _obj):
        return None


def _tx(type_=TransactionType.debit, source="davivienda", amount="120000"):
    return SimpleNamespace(
        id=uuid.uuid4(), amount=Decimal(amount), merchant="Cena", category="food",
        transaction_type=type_, currency="COP", card_last_digits=None,
        occurred_at=datetime(2026, 11, 22, tzinfo=timezone.utc), note=None, debt_id=None,
        source=source, shared_amount=None, contact_id=None, shares=[],
    )


def _patch(row, body):
    session = _Session(row)
    app = FastAPI()
    app.include_router(transactions.router)
    app.dependency_overrides[deps.get_current_user] = lambda: SimpleNamespace(id=uuid.uuid4())
    app.dependency_overrides[deps.get_db] = lambda: session
    return TestClient(app).patch(f"/transactions/{row.id}", json=body), session


ANA, LUIS = str(uuid.uuid4()), str(uuid.uuid4())


def test_split_among_two_sets_the_sum_and_each_part() -> None:
    row = _tx()
    resp, session = _patch(
        row, {"shares": [{"contact_id": ANA, "amount": "30000"},
                         {"contact_id": LUIS, "amount": "30000"}]}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert Decimal(body["shared_amount"]) == Decimal("60000")
    assert body["contact_id"] is None
    assert {s["contact_id"] for s in body["shares"]} == {ANA, LUIS}
    assert session.committed


def test_single_share_names_the_person() -> None:
    row = _tx()
    resp, _ = _patch(row, {"shares": [{"contact_id": ANA, "amount": "40000"}]})
    assert resp.status_code == 200
    assert resp.json()["contact_id"] == ANA


def test_empty_shares_clears_the_split() -> None:
    row = _tx()
    row.shared_amount = Decimal("60000")
    row.shares = [TransactionShare(contact_id=uuid.UUID(ANA), amount=Decimal("60000"))]
    resp, _ = _patch(row, {"shares": []})
    assert resp.status_code == 200
    assert resp.json()["shared_amount"] is None
    assert resp.json()["shares"] == []


def test_parts_cannot_exceed_the_total() -> None:
    resp, session = _patch(
        _tx(amount="50000"),
        {"shares": [{"contact_id": ANA, "amount": "30000"},
                    {"contact_id": LUIS, "amount": "30000"}]},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "shared_exceeds_amount"
    assert not session.committed


def test_same_person_twice_is_refused() -> None:
    resp, _ = _patch(
        _tx(), {"shares": [{"contact_id": ANA, "amount": "1"}, {"contact_id": ANA, "amount": "2"}]}
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "duplicate_share_contact"


def test_credits_and_what_a_contact_paid_cannot_be_split() -> None:
    body = {"shares": [{"contact_id": ANA, "amount": "1000"}]}
    assert _patch(_tx(type_=TransactionType.credit), body)[0].status_code == 422
    assert _patch(_tx(source="contact"), body)[0].status_code == 422


def test_each_share_raises_its_own_persons_balance() -> None:
    ana, luis = uuid.uuid4(), uuid.uuid4()
    row = _tx()
    row.shared_amount = Decimal("70000")
    row.shares = [
        SimpleNamespace(contact_id=ana, amount=Decimal("30000")),
        SimpleNamespace(contact_id=luis, amount=Decimal("40000")),
    ]
    assert balance_effects(row, None) == [(ana, Decimal("30000")), (luis, Decimal("40000"))]


def test_unsplit_rows_keep_the_one_person_rule() -> None:
    jesus = uuid.uuid4()
    row = _tx()
    row.shared_amount = Decimal("48925")
    assert balance_effects(row, jesus) == [(jesus, Decimal("48925"))]
    assert balance_effects(row, None) == []
