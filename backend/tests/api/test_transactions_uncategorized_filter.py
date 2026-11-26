"""GET /transactions?category=__none__ lists movements with no category."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import deps
from app.api.routes import transactions


class _Result:
    def scalar_one(self):
        return 0

    def scalars(self):
        return SimpleNamespace(all=lambda: [])


class _Session:
    def __init__(self):
        self.sql: list[str] = []

    async def execute(self, stmt):
        self.sql.append(str(stmt.compile(compile_kwargs={"literal_binds": True})))
        return _Result()


def _list(category: str) -> _Session:
    session = _Session()
    app = FastAPI()
    app.include_router(transactions.router)
    app.dependency_overrides[deps.get_current_user] = lambda: SimpleNamespace(id=uuid.uuid4())
    app.dependency_overrides[deps.get_db] = lambda: session
    assert TestClient(app).get("/transactions", params={"category": category}).status_code == 200
    return session


def test_uncategorized_filters_null_category() -> None:
    sql = " ".join(_list("__none__").sql)
    assert "transactions.category IS NULL" in sql
    assert "'__none__'" not in sql


def test_a_category_filters_by_its_slug() -> None:
    assert "transactions.category = 'otros'" in " ".join(_list("otros").sql)
