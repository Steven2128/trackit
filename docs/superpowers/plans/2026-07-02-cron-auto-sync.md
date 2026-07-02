# Cron Auto-Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run `POST /gmail/sync`'s existing service on a `SYNC_INTERVAL_HOURS` schedule for every connected Gmail account, starting immediately at backend boot.

**Architecture:** APScheduler's `AsyncIOScheduler` starts inside FastAPI's `lifespan` context manager. A single job (`sync_all_users_job`) queries all connected `ProviderConnection` rows and calls the existing `sync_provider_connection` service once per connection, in its own DB session, with per-user failure isolation.

**Tech Stack:** FastAPI (lifespan), APScheduler 3.x (`AsyncIOScheduler` + `IntervalTrigger`), SQLAlchemy 2.0 async, pytest + pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-07-02-cron-auto-sync-design.md`

**Working dir:** All backend commands run inside the docker-compose backend container: `docker compose run --rm backend <cmd>`.

---

## File map

**New files:**
- `backend/app/services/scheduler.py`
- `backend/tests/conftest.py`
- `backend/tests/services/test_scheduler.py`

**Modified files:**
- `backend/pyproject.toml` (add `apscheduler>=3.10`)
- `backend/app/core/config.py` (two new settings)
- `backend/app/main.py` (`lifespan` wiring)

---

### Task 1: Add APScheduler dependency

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Add `apscheduler>=3.10` to `dependencies`**

Old (lines 11–26 of `backend/pyproject.toml`):
```toml
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30",
    "alembic>=1.14",
    "pydantic[email]>=2.9",
    "pydantic-settings>=2.6",
    "python-jose[cryptography]>=3.3",
    "cryptography>=43",
    "google-auth>=2.35",
    "google-auth-oauthlib>=1.2",
    "google-api-python-client>=2.150",
    "httpx>=0.27",
    "python-multipart>=0.0.20",
]
```

New (add `apscheduler>=3.10` at the end of the list, keep alphabetical is not enforced in the current file — append is fine):
```toml
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30",
    "alembic>=1.14",
    "pydantic[email]>=2.9",
    "pydantic-settings>=2.6",
    "python-jose[cryptography]>=3.3",
    "cryptography>=43",
    "google-auth>=2.35",
    "google-auth-oauthlib>=1.2",
    "google-api-python-client>=2.150",
    "httpx>=0.27",
    "python-multipart>=0.0.20",
    "apscheduler>=3.10",
]
```

- [ ] **Step 2: Rebuild the backend image so the dep lands in the container**

Run from repo root:
```bash
docker compose build backend
```
Expected: image rebuilds; last lines show `Successfully tagged trackit-backend:latest` (or similar).

- [ ] **Step 3: Verify the module imports inside the container**

```bash
docker compose run --rm backend python -c "import apscheduler; print(apscheduler.__version__)"
```
Expected: prints a version string like `3.10.4`, exits 0.

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml
git commit -m "chore(backend): add apscheduler dependency"
```

---

### Task 2: Add scheduler settings to config

**Files:**
- Modify: `backend/app/core/config.py`

- [ ] **Step 1: Add the two settings fields**

Old (lines 30–34 of `backend/app/core/config.py`):
```python
    gmail_sync_default_lookback_days: int = 30
    gmail_sync_max_messages: int = 200

    user_timezone: str = Field(default="America/Bogota")
```

New — insert the two scheduler fields right after `gmail_sync_max_messages`:
```python
    gmail_sync_default_lookback_days: int = 30
    gmail_sync_max_messages: int = 200

    sync_interval_hours: int = Field(default=6)
    sync_scheduler_enabled: bool = Field(default=True)

    user_timezone: str = Field(default="America/Bogota")
```

- [ ] **Step 2: Verify settings load with defaults**

```bash
docker compose run --rm backend python -c "from app.core.config import settings; print(settings.sync_interval_hours, settings.sync_scheduler_enabled)"
```
Expected: `6 True`, exit 0.

- [ ] **Step 3: Verify env overrides work**

```bash
docker compose run --rm -e SYNC_INTERVAL_HOURS=2 -e SYNC_SCHEDULER_ENABLED=false backend python -c "from app.core.config import settings; print(settings.sync_interval_hours, settings.sync_scheduler_enabled)"
```
Expected: `2 False`, exit 0.

- [ ] **Step 4: Commit**

```bash
git add backend/app/core/config.py
git commit -m "feat(backend): add sync scheduler settings"
```

---

### Task 3: Add `tests/conftest.py` to disable scheduler in tests

**Files:**
- Create: `backend/tests/conftest.py`

Currently `backend/tests/conftest.py` does not exist. Once the scheduler is wired into `main.py` (Task 5), any test that imports the FastAPI app would start it. Prevent that by setting the env var before `settings` is instantiated for the first time in a test run.

- [ ] **Step 1: Create the file**

```python
# backend/tests/conftest.py
import os

os.environ.setdefault("SYNC_SCHEDULER_ENABLED", "false")
```

The `setdefault` guard means a developer who explicitly wants the scheduler on during a test run can still set `SYNC_SCHEDULER_ENABLED=true` before invoking pytest.

- [ ] **Step 2: Run the existing suite to confirm nothing regressed**

```bash
docker compose run --rm backend pytest tests/ -q
```
Expected: all existing tests pass (scheduler isn't wired yet, so this is really just a smoke check that the new conftest doesn't break collection).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "test(backend): disable scheduler by default in test env"
```

---

### Task 4: Write failing test for `sync_all_users_job`

**Files:**
- Create: `backend/tests/services/test_scheduler.py`

**Design note:** the existing test suite does NOT use a real DB — parser tests read `.eml` fixtures and the categorizer test is pure-function. Follow that pattern here: mock `AsyncSessionLocal` and `sync_provider_connection` entirely, so this test does not depend on Postgres or migrations. The goal is to prove the loop's failure-isolation and iteration order, not to exercise SQLAlchemy.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/services/test_scheduler.py
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
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
docker compose run --rm backend pytest tests/services/test_scheduler.py -v
```
Expected: `ModuleNotFoundError: No module named 'app.services.scheduler'` (both tests error at import).

---

### Task 5: Implement `app/services/scheduler.py`

**Files:**
- Create: `backend/app/services/scheduler.py`

- [ ] **Step 1: Write the module**

```python
# backend/app/services/scheduler.py
"""Auto-sync scheduler.

`sync_all_users_job` runs on the interval configured by `SYNC_INTERVAL_HOURS`
(default 6). It walks every connected Gmail `ProviderConnection` and invokes
`sync_provider_connection` — the same service the manual `POST /gmail/sync`
endpoint uses — in its own session, with per-connection failure isolation.

Timezone note: APScheduler defaults its `IntervalTrigger` to the process
timezone. We pass `next_run_time` in UTC to guarantee the first run fires
immediately regardless of the container's TZ.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.provider_connection import ProviderConnection, ProviderType
from app.services.email_sync import sync_provider_connection

log = logging.getLogger(__name__)


async def sync_all_users_job() -> None:
    """Iterate all connected Gmail accounts and sync each one.

    One bad connection (revoked token, network error, malformed row) must
    never stop the batch. Errors are logged with `user_id` and
    `connection_id` and the loop continues.
    """
    started = time.monotonic()
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ProviderConnection.id).where(
                ProviderConnection.provider_type == ProviderType.gmail,
                ProviderConnection.refresh_token_encrypted.is_not(None),
            )
        )
        connection_ids = list(result.scalars())

    ok = 0
    failed = 0
    for connection_id in connection_ids:
        async with AsyncSessionLocal() as db:
            connection = await db.get(ProviderConnection, connection_id)
            if connection is None:
                continue
            try:
                await sync_provider_connection(
                    db,
                    connection,
                    fallback_lookback_days=settings.gmail_sync_default_lookback_days,
                    max_messages=settings.gmail_sync_max_messages,
                )
                ok += 1
            except Exception:  # noqa: BLE001 — one bad user must not stop the batch
                log.exception(
                    "sync_all_users_job connection_failed",
                    extra={
                        "user_id": str(connection.user_id),
                        "connection_id": str(connection.id),
                    },
                )
                failed += 1

    duration_ms = int((time.monotonic() - started) * 1000)
    log.info(
        "sync_all_users_job completed",
        extra={
            "total": len(connection_ids),
            "ok": ok,
            "failed": failed,
            "duration_ms": duration_ms,
        },
    )


def build_scheduler() -> AsyncIOScheduler:
    """Return an unstarted scheduler. Caller adds jobs and calls `.start()`."""
    return AsyncIOScheduler(timezone=timezone.utc)
```

- [ ] **Step 2: Run the test to verify it passes**

```bash
docker compose run --rm backend pytest tests/services/test_scheduler.py -v
```
Expected: `test_sync_all_users_job_isolates_per_connection_failures PASSED`.

- [ ] **Step 3: Run the full suite to check nothing else broke**

```bash
docker compose run --rm backend pytest tests/ -q
```
Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/scheduler.py backend/tests/services/test_scheduler.py
git commit -m "feat(backend): add sync_all_users_job with per-connection isolation"
```

---

### Task 6: Wire scheduler into FastAPI `lifespan`

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Replace the file**

Old `backend/app/main.py`:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, dashboard, debts, gmail, transactions
from app.core.config import settings
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="TrackIt API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth.router)
    app.include_router(gmail.router)
    app.include_router(transactions.router)
    app.include_router(debts.router)
    app.include_router(dashboard.router)

    return app


app = create_app()
```

New:
```python
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, dashboard, debts, gmail, transactions
from app.core.config import settings
from app.core.logging import configure_logging
from app.services.scheduler import build_scheduler, sync_all_users_job

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = None
    if settings.sync_scheduler_enabled:
        scheduler = build_scheduler()
        scheduler.add_job(
            sync_all_users_job,
            IntervalTrigger(hours=settings.sync_interval_hours),
            next_run_time=datetime.now(timezone.utc),
            id="gmail_sync_all_users",
            replace_existing=True,
        )
        scheduler.start()
        log.info(
            "sync_scheduler_started",
            extra={"interval_hours": settings.sync_interval_hours},
        )
    else:
        log.info("sync_scheduler_disabled")

    yield

    if scheduler is not None:
        scheduler.shutdown(wait=False)
        log.info("sync_scheduler_stopped")


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="TrackIt API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth.router)
    app.include_router(gmail.router)
    app.include_router(transactions.router)
    app.include_router(debts.router)
    app.include_router(dashboard.router)

    return app


app = create_app()
```

- [ ] **Step 2: Run the full test suite (scheduler must be off in tests)**

```bash
docker compose run --rm backend pytest tests/ -q
```
Expected: all tests pass. If any test hangs, the `SYNC_SCHEDULER_ENABLED=false` in `tests/conftest.py` from Task 3 isn't taking effect — investigate before proceeding.

- [ ] **Step 3: Boot the backend and confirm the scheduler starts**

```bash
docker compose up -d backend
docker compose logs backend | tail -50
```
Expected: within a few seconds after boot, log lines appear:
- `sync_scheduler_started ... interval_hours=6`
- Then either `sync_all_users_job completed total=0 ok=0 failed=0 duration_ms=...` (no gmail connections yet) or per-connection log lines if there is a connection.

- [ ] **Step 4: Confirm HTTP still works**

```bash
curl -s http://localhost:8000/health
```
Expected: `{"status":"ok"}`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py
git commit -m "feat(backend): start sync scheduler in FastAPI lifespan"
```

---

### Task 7: Verify the `SYNC_SCHEDULER_ENABLED=false` escape hatch

**Files:** none — verification only.

- [ ] **Step 1: Stop and restart backend with scheduler disabled**

```bash
docker compose stop backend
SYNC_SCHEDULER_ENABLED=false docker compose up -d backend
docker compose logs backend | tail -20
```
Expected: log line `sync_scheduler_disabled` appears. No `sync_scheduler_started` line, no `sync_all_users_job` runs.

- [ ] **Step 2: Restart backend with scheduler on again (default)**

```bash
docker compose stop backend
docker compose up -d backend
docker compose logs backend | tail -20
```
Expected: `sync_scheduler_started` line reappears; a `sync_all_users_job completed` line follows within seconds (from the immediate `next_run_time`).

- [ ] **Step 3: If a Gmail connection exists, confirm it was synced**

```bash
docker compose exec db psql -U trackit -d trackit -c "SELECT provider_email, last_sync_at FROM provider_connections;"
```
Expected: `last_sync_at` is within the last minute or two for each row.

If there are no rows, this step is a no-op — the aggregate log line will show `total=0`, which is correct.

- [ ] **Step 4: Commit any polish fixes (if any)**

If Steps 1–3 revealed issues that required tweaks, commit them:
```bash
git add <changed-files>
git commit -m "fix(backend): <specific issue>"
```

If everything worked, no commit here.

---

## Verification summary

| Task | Verification |
|---|---|
| 1 | `import apscheduler` succeeds inside container |
| 2 | Settings load defaults; env overrides work |
| 3 | `pytest tests/` still passes with new conftest |
| 4 | New test fails with `ModuleNotFoundError` for `app.services.scheduler` |
| 5 | New test passes; whole suite passes |
| 6 | Suite still passes; backend boots; `sync_scheduler_started` in logs; first job run logged |
| 7 | `SYNC_SCHEDULER_ENABLED=false` suppresses scheduler; re-enable path works |

---

## Risks and rollback

- **Startup ordering**: `sync_all_users_job` fires immediately at boot. If the DB isn't ready yet, the first run will log an exception and the interval kicks in later. Docker-compose already declares the backend `depends_on` db; the risk is negligible.
- **Duplicate schedulers**: `replace_existing=True` on `add_job` guards against a stale job id, but running two backend containers against the same DB would double-sync. Out of scope — deployment is single-container.
- **Test hang**: if `SYNC_SCHEDULER_ENABLED=false` doesn't propagate to `settings` (e.g., `settings` was cached before conftest ran), tests could try to spin up an event loop for the scheduler. Mitigation: `settings` is created lazily via `get_settings()` with `lru_cache`; conftest sets the env var at import time, before any test imports `app.core.config`.
- **Rollback per task**: each task is a single commit. `git revert <hash>` cleanly reverts an individual step. To fully disable the feature without a revert: set `SYNC_SCHEDULER_ENABLED=false` in `.env` and restart.
