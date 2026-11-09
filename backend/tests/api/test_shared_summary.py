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


class _Scalar:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value

    def scalars(self):
        return SimpleNamespace(all=lambda: self.value)


class _Session:
    """Answers the queries in order: shared sum, reimbursed sum, contacts,
    rows naming a contact, listed rows."""

    def __init__(self, *answers):
        self.answers = list(answers)

    async def execute(self, _stmt):
        return _Scalar(self.answers.pop(0))


def _row(amount, type_, category=None, shared=None):
    return SimpleNamespace(
        id=uuid.uuid4(), amount=Decimal(amount), merchant="Luz", category=category,
        transaction_type=type_, currency="COP", card_last_digits=None,
        occurred_at=datetime(2026, 11, 7, tzinfo=timezone.utc), note=None,
        debt_id=None, source="davivienda", contact_id=None,
        shared_amount=Decimal(shared) if shared else None,
    )


def _get(session):
    app = FastAPI()
    app.include_router(transactions.router)
    app.dependency_overrides[deps.get_current_user] = lambda: SimpleNamespace(id=uuid.uuid4())
    app.dependency_overrides[deps.get_db] = lambda: session
    return TestClient(app).get("/transactions/shared")


def test_pending_is_what_others_covered_minus_what_came_back() -> None:
    rows = [
        _row("97850", TransactionType.debit, "bills", "48925"),
        _row("550000", TransactionType.credit, "reimbursement"),
    ]
    resp = _get(_Session(Decimal("706800"), Decimal("550000"), [], [], rows))

    assert resp.status_code == 200
    body = resp.json()
    assert Decimal(body["covered_for_others"]) == Decimal("706800")
    assert Decimal(body["reimbursed"]) == Decimal("550000")
    assert Decimal(body["pending"]) == Decimal("156800")
    assert len(body["items"]) == 2


def test_overpaid_never_goes_negative() -> None:
    resp = _get(_Session(Decimal("100"), Decimal("500"), [], [], []))

    assert Decimal(resp.json()["pending"]) == 0


def test_people_get_their_own_balance() -> None:
    jesus = SimpleNamespace(id=uuid.uuid4(), name="Jesús")
    diego = SimpleNamespace(id=uuid.uuid4(), name="Diego")
    named = [
        # Luz 97.850 paid by the user, half his → he owes 48.925.
        SimpleNamespace(**{**vars(_row("97850", TransactionType.debit, "bills", "48925")),
                           "contact_id": jesus.id}),
        # Groceries 60.000 he paid, half the user's → user owes 30.000.
        SimpleNamespace(**{**vars(_row("60000", TransactionType.debit, "food", "30000")),
                           "contact_id": jesus.id, "source": "contact"}),
    ]
    resp = _get(_Session(Decimal("0"), Decimal("0"), [diego, jesus], named, []))
    people = resp.json()["people"]
    assert [p["name"] for p in people] == ["Jesús", "Diego"]
    assert Decimal(people[0]["balance"]) == Decimal("18925")
    assert Decimal(people[1]["balance"]) == 0
