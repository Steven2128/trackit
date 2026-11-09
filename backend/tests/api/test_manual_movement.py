"""POST /transactions/manual: paybacks by "llave" with no email, money lent,
and expenses a contact paid."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import deps
from app.api.routes import transactions
from app.models.account import AccountKind
from app.models.transaction import TransactionType

CONTACT = uuid.uuid4()
WHEN = "2026-11-03T15:00:00+00:00"
WHEN_DT = datetime(2026, 11, 3, 15, tzinfo=timezone.utc)


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _Session:
    """Every lookup finds the user's contact (or the row under edit)."""

    def __init__(self, row=None):
        self.row = row
        self.added = []
        self.deleted = []
        self.committed = False

    async def execute(self, _stmt):
        return _Result(self.row if self.row is not None else CONTACT)

    def add(self, obj):
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def commit(self):
        self.committed = True

    async def refresh(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()


@pytest.fixture(autouse=True)
def reconciled(monkeypatch):
    calls = []

    async def _bank(_db, _user, kind, before, after):
        calls.append((kind, before, after))

    async def _cash(_db, _user, before, after):
        calls.append((AccountKind.cash, before, after))

    monkeypatch.setattr(transactions, "keep_reconciled", _bank)
    monkeypatch.setattr(transactions, "keep_cash_reconciled", _cash)
    return calls


def _client(session):
    app = FastAPI()
    app.include_router(transactions.router)
    app.dependency_overrides[deps.get_current_user] = lambda: SimpleNamespace(id=uuid.uuid4())
    app.dependency_overrides[deps.get_db] = lambda: session
    return TestClient(app)


def _post(session, **body):
    base = {"merchant": "Devolución boleta", "occurred_at": WHEN}
    return _client(session).post("/transactions/manual", json={**base, **body})


def test_payback_by_llave_lands_in_davivienda_as_reimbursement(reconciled) -> None:
    session = _Session()
    resp = _post(
        session, account="davivienda", transaction_type="credit", amount="40000",
        category="reimbursement", contact_id=str(CONTACT),
    )
    assert resp.status_code == 201, resp.text
    tx = session.added[0]
    assert (tx.source, tx.category, tx.contact_id) == ("davivienda", "reimbursement", CONTACT)
    assert resp.json()["manual"] is True
    # A credit is a negative outflow for the reconciliation.
    assert reconciled == [(AccountKind.davivienda, None, (Decimal("-40000"), WHEN_DT))]
    assert session.committed


def test_expense_the_contact_paid_moves_no_account(reconciled) -> None:
    session = _Session()
    resp = _post(
        session, account="contact", transaction_type="debit", amount="60000",
        category="food", contact_id=str(CONTACT), shared_amount="30000",
    )
    assert resp.status_code == 201, resp.text
    tx = session.added[0]
    assert (tx.source, tx.shared_amount) == ("contact", Decimal("30000"))
    assert reconciled == []


def test_contact_paid_needs_the_contact() -> None:
    resp = _post(_Session(), account="contact", transaction_type="debit", amount="60000")
    assert resp.status_code == 422


def test_contact_paid_cant_be_a_credit() -> None:
    resp = _post(
        _Session(), account="contact", transaction_type="credit", amount="60000",
        contact_id=str(CONTACT),
    )
    assert resp.status_code == 422


def test_their_part_cant_exceed_the_total() -> None:
    resp = _post(
        _Session(), account="contact", transaction_type="debit", amount="60000",
        contact_id=str(CONTACT), shared_amount="70000",
    )
    assert resp.status_code == 422


def test_unknown_contact_is_404() -> None:
    class _NoContact(_Session):
        async def execute(self, _stmt):
            return _Result(None)

    resp = _post(
        _NoContact(), account="davivienda", transaction_type="credit", amount="1",
        contact_id=str(uuid.uuid4()),
    )
    assert resp.status_code == 404


def _typed_row(**over):
    base = dict(
        id=uuid.uuid4(), amount=Decimal("40000"), merchant="Devolución", category="reimbursement",
        transaction_type=TransactionType.credit, currency="COP", card_last_digits=None,
        occurred_at=WHEN_DT, note=None, debt_id=None, source="davivienda",
        shared_amount=None, contact_id=None, manual=True,
    )
    base.update(over)
    return SimpleNamespace(**base)


def test_typed_bank_row_amount_is_editable_and_stays_reconciled(reconciled) -> None:
    row = _typed_row()
    resp = _client(_Session(row)).patch(f"/transactions/{row.id}", json={"amount": "45000"})
    assert resp.status_code == 200, resp.text
    assert reconciled == [
        (AccountKind.davivienda, (Decimal("-40000"), WHEN_DT), (Decimal("-45000"), WHEN_DT))
    ]


def test_email_bank_row_amount_stays_locked() -> None:
    row = _typed_row(manual=False)
    resp = _client(_Session(row)).patch(f"/transactions/{row.id}", json={"amount": "45000"})
    assert resp.status_code == 409


def test_typed_bank_row_can_be_deleted(reconciled) -> None:
    row = _typed_row()
    session = _Session(row)
    assert _client(session).delete(f"/transactions/{row.id}").status_code == 204
    assert session.deleted == [row]
    assert reconciled == [(AccountKind.davivienda, (Decimal("-40000"), WHEN_DT), None)]


def test_contact_paid_row_keeps_its_contact() -> None:
    row = _typed_row(source="contact", transaction_type=TransactionType.debit, contact_id=CONTACT)
    resp = _client(_Session(row)).patch(f"/transactions/{row.id}", json={"contact_id": None})
    assert resp.status_code == 422
