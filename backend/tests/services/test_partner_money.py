from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.models.fund_hold import FundHold
from app.services.partner_money import hold_partner_money


class _Result:
    def __init__(self, value):
        self._value = value

    def scalars(self):
        return self

    def all(self):
        return self._value

    def first(self):
        return self._value


class _FakeSession:
    """Answers each SELECT with the next queued value."""

    def __init__(self, *values):
        self._values = list(values)
        self.added = []
        self.committed = False

    async def execute(self, _stmt):
        return _Result(self._values.pop(0))

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True


RENT = SimpleNamespace(id=uuid.uuid4(), name="Arriendo", partner_amount=Decimal("550000"))
NOW = datetime(2026, 12, 5, 20, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_matching_deposit_becomes_a_hold_and_stops_being_income() -> None:
    deposit = SimpleNamespace(category=None, note=None)
    session = _FakeSession([RENT], None, deposit)  # payments, no hold yet, the deposit
    assert await hold_partner_money(session, uuid.uuid4(), NOW) == 1
    assert deposit.category == "reimbursement"
    (hold,) = session.added
    assert isinstance(hold, FundHold)
    assert (hold.amount, hold.planned_payment_id) == (Decimal("550000"), RENT.id)
    assert session.committed


@pytest.mark.asyncio
async def test_waits_while_the_previous_part_is_still_held() -> None:
    session = _FakeSession([RENT], (uuid.uuid4(),))  # a hold exists: no deposit lookup
    assert await hold_partner_money(session, uuid.uuid4(), NOW) == 0
    assert session.added == [] and not session.committed


@pytest.mark.asyncio
async def test_nothing_to_do_without_a_deposit() -> None:
    session = _FakeSession([RENT], None, None)
    assert await hold_partner_money(session, uuid.uuid4(), NOW) == 0
    assert session.added == []
