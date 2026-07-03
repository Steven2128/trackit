from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import patch

import pytest


def _fake_connection(user_id: uuid.UUID, connection_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(id=connection_id, user_id=user_id)


class _FakeSession:
    """Stand-in for AsyncSession supporting the two calls the job makes."""

    def __init__(self, ids: list[uuid.UUID], connections: dict[uuid.UUID, SimpleNamespace]):
        self._ids = ids
        self._connections = connections

    async def execute(self, _stmt):
        ids = self._ids

        class _Result:
            def scalars(self_inner):
                return ids

        return _Result()

    async def get(self, _model, connection_id: uuid.UUID):
        return self._connections.get(connection_id)


def _make_sessionmaker(ids: list[uuid.UUID], connections: dict[uuid.UUID, SimpleNamespace]):
    @asynccontextmanager
    async def _cm():
        yield _FakeSession(ids, connections)

    # Match the `AsyncSessionLocal()` call pattern — a callable that returns an async CM.
    return lambda: _cm()


@pytest.mark.asyncio
async def test_sync_all_users_job_isolates_per_connection_failures():
    """One connection failing must not stop the other from being synced."""
    user_ok_id = uuid.uuid4()
    user_bad_id = uuid.uuid4()
    conn_ok_id = uuid.uuid4()
    conn_bad_id = uuid.uuid4()
    ids = [conn_ok_id, conn_bad_id]
    connections = {
        conn_ok_id: _fake_connection(user_ok_id, conn_ok_id),
        conn_bad_id: _fake_connection(user_bad_id, conn_bad_id),
    }

    fake_sessionmaker = _make_sessionmaker(ids, connections)
    call_log: list[uuid.UUID] = []

    async def fake_sync(db, connection, *, fallback_lookback_days, max_messages):
        call_log.append(connection.id)
        if connection.id == conn_bad_id:
            raise RuntimeError("simulated gmail 401")
        return None

    with (
        patch("app.services.scheduler.AsyncSessionLocal", fake_sessionmaker),
        patch("app.services.scheduler.sync_provider_connection", side_effect=fake_sync),
    ):
        from app.services.scheduler import sync_all_users_job

        await sync_all_users_job()

    assert call_log == [conn_ok_id, conn_bad_id]


@pytest.mark.asyncio
async def test_sync_all_users_job_empty_connections_no_op():
    """With zero connections, the job completes cleanly without touching sync."""
    fake_sessionmaker = _make_sessionmaker([], {})
    called = False

    async def fake_sync(*args, **kwargs):
        nonlocal called
        called = True

    with (
        patch("app.services.scheduler.AsyncSessionLocal", fake_sessionmaker),
        patch("app.services.scheduler.sync_provider_connection", side_effect=fake_sync),
    ):
        from app.services.scheduler import sync_all_users_job

        await sync_all_users_job()

    assert called is False
