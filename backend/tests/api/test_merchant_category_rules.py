from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import deps
from app.api.routes import merchant_category_rules


class _Scalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return _Scalars(self._rows)


class _FakeSession:
    """Answers the route's two SELECTs in order: the user's rules, then
    their transactions."""

    def __init__(self, rules, txs):
        self._results = [rules, txs]
        self.added = []
        self.committed = False

    async def execute(self, _stmt):
        return _Result(self._results.pop(0))

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True

    async def refresh(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        if getattr(obj, "created_at", None) is None:
            obj.created_at = "2026-10-19T21:00:00+00:00"


def _tx(merchant, category):
    return SimpleNamespace(merchant=merchant, category=category)


def _client(session) -> TestClient:
    app = FastAPI()
    app.include_router(merchant_category_rules.router)
    app.dependency_overrides[deps.get_current_user] = lambda: SimpleNamespace(id=uuid.uuid4())
    app.dependency_overrides[deps.get_db] = lambda: session
    return TestClient(app)


def test_apply_to_past_moves_only_untouched_matches() -> None:
    txs = [
        _tx("TIENDA D1 LA FLORIDA", "food"),  # automatic → moves
        _tx("COMPRA TIENDA D1 LA FLORIDA A As", "food"),  # automatic → moves
        _tx("TIENDAS D1 MED TARAPAC", "galguerias"),  # chosen by hand → stays
        _tx("RAPPI COLOMBIA*DL", "food"),  # other merchant → stays
        _tx("D1 TRANSFER", "transfer"),  # parser's call → stays
    ]
    session = _FakeSession(rules=[], txs=txs)
    resp = _client(session).post(
        "/category-rules", json={"pattern": "D1", "category": "mercado", "apply_to_past": True}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["updated"] == 2
    assert body["rule"]["pattern"] == "d1"
    assert [t.category for t in txs] == ["mercado", "mercado", "galguerias", "food", "transfer"]
    assert session.committed


def test_rule_for_the_future_only_leaves_past_alone() -> None:
    txs = [_tx("TIENDA D1 LA FLORIDA", "food")]
    session = _FakeSession(rules=[], txs=txs)
    resp = _client(session).post("/category-rules", json={"pattern": "d1", "category": "mercado"})
    assert resp.status_code == 200
    assert resp.json()["updated"] == 0
    assert txs[0].category == "food"
    (rule,) = session.added
    assert (rule.pattern, rule.category) == ("d1", "mercado")


def test_existing_pattern_is_updated_not_duplicated() -> None:
    existing = SimpleNamespace(
        id=uuid.uuid4(), pattern="d1", category="mercado",
        created_at="2026-10-19T21:00:00+00:00",
    )
    txs = [_tx("TIENDA D1", "mercado"), _tx("TIENDA D1 CENTRO", "galguerias")]
    session = _FakeSession(rules=[existing], txs=txs)
    resp = _client(session).post(
        "/category-rules", json={"pattern": "d1", "category": "hogar", "apply_to_past": True}
    )
    assert resp.status_code == 200
    assert session.added == []
    assert existing.category == "hogar"
    # What the rule had moved follows it; the hand-picked one stays.
    assert [t.category for t in txs] == ["hogar", "galguerias"]


@pytest.mark.parametrize(
    "payload,detail",
    [
        ({"pattern": "***", "category": "mercado"}, "invalid_pattern"),
        ({"pattern": "d1", "category": "transfer"}, "unknown_category"),
        ({"pattern": "d1", "category": "Mercado Bonito"}, "unknown_category"),
    ],
)
def test_invalid_rules_are_422(payload, detail) -> None:
    session = _FakeSession(rules=[], txs=[])
    resp = _client(session).post("/category-rules", json=payload)
    assert resp.status_code == 422
    assert resp.json()["detail"] == detail
    assert not session.committed


def test_suggestion_endpoint() -> None:
    resp = _client(_FakeSession([], [])).get(
        "/category-rules/suggestion", params={"merchant": "COMPRA TIENDA D1 LA FLORIDA A As"}
    )
    assert resp.status_code == 200
    assert resp.json() == {"pattern": "d1"}
