# Cron Auto-Sync — Design Spec

**Date:** 2026-07-02
**Status:** Approved
**Related roadmap item:** Sprint 4 — "Sync automático con cron (cada 6 horas)"

## Problem

`POST /gmail/sync` today requires a manual invocation (mobile "Sync now" or curl). To keep transactions fresh without the user opening the app, the backend needs to run the same sync flow on a schedule for every connected Gmail account.

## Non-goals

- Multi-provider polling beyond Gmail (only `provider_type=gmail` connections are in scope).
- Retries / dead-letter queue: a failure on one interval is retried on the next.
- Distributed / horizontal scaling: the app runs in a single container.
- Persistent job store: the schedule is fixed and re-created on each startup.

## Approach

APScheduler's `AsyncIOScheduler` running inside the FastAPI process, wired through the FastAPI `lifespan` context manager. The scheduled job iterates connected accounts and reuses the existing `sync_provider_connection` service — the same code path that `POST /gmail/sync` uses today.

Rejected alternatives:
- **Celery + Redis** — more moving parts than a single-instance app needs.
- **External cron hitting an HTTP endpoint** — requires an internal auth surface and doesn't compose with the async DB session lifecycle.

## Components

### 1. Dependency

Add to `backend/pyproject.toml` `dependencies`:

```
apscheduler>=3.10
```

### 2. Settings (`app/core/config.py`)

Add two fields:

```python
sync_interval_hours: int = Field(default=6)
sync_scheduler_enabled: bool = Field(default=True)
```

- `SYNC_INTERVAL_HOURS` — env override for the interval (default 6).
- `SYNC_SCHEDULER_ENABLED` — env override to disable the scheduler entirely (used in tests and for local dev where sync noise is unwanted).

### 3. New module `app/services/scheduler.py`

Two functions:

```python
async def sync_all_users_job() -> None: ...
def build_scheduler() -> AsyncIOScheduler: ...
```

**`sync_all_users_job`:**
1. Open a short-lived `AsyncSession` via `AsyncSessionLocal` to query IDs only:
   ```python
   async with AsyncSessionLocal() as db:
       result = await db.execute(
           select(ProviderConnection.id).where(
               ProviderConnection.provider_type == ProviderType.gmail,
               ProviderConnection.refresh_token_encrypted.is_not(None),
           )
       )
       connection_ids = list(result.scalars())
   ```
   The job runs outside a request scope — do NOT use FastAPI's `DbSession` dependency.
2. For each `connection_id`, open a fresh session and re-query the ORM object inside it (ORM objects cannot be shared across sessions):
   ```python
   for connection_id in connection_ids:
       async with AsyncSessionLocal() as db:
           connection = await db.get(ProviderConnection, connection_id)
           if connection is None:
               continue
           try:
               await sync_provider_connection(
                   db, connection,
                   fallback_lookback_days=settings.gmail_sync_default_lookback_days,
                   max_messages=settings.gmail_sync_max_messages,
               )
               ok += 1
           except Exception:  # noqa: BLE001 — one bad user must not stop the batch
               logger.exception(
                   "sync_all_users_job connection_failed",
                   extra={"user_id": str(connection.user_id), "connection_id": str(connection.id)},
               )
               failed += 1
   ```
3. Log an aggregate line at the end: `logger.info("sync_all_users_job completed", extra={"total": total, "ok": ok, "failed": failed, "duration_ms": ms})`.

**`build_scheduler`:**
- Constructs and returns an `AsyncIOScheduler`.
- Does NOT start the scheduler and does NOT add jobs — the caller (in `main.py`) handles that so the wire-up is testable.

### 4. Wire-up in `app/main.py`

Convert the current `create_app()` into a factory that installs a FastAPI `lifespan`:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = None
    if settings.sync_scheduler_enabled:
        scheduler = build_scheduler()
        scheduler.add_job(
            sync_all_users_job,
            IntervalTrigger(hours=settings.sync_interval_hours),
            next_run_time=datetime.now(timezone.utc),  # run immediately on boot
            id="gmail_sync_all_users",
            replace_existing=True,
        )
        scheduler.start()
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)
```

Attach with `FastAPI(lifespan=lifespan, ...)`. The rest of `create_app()` stays the same.

### 5. Test hygiene

- `backend/tests/conftest.py` (or add if missing) must set `SYNC_SCHEDULER_ENABLED=false` before `settings` is instantiated — either via a `.env.test` file, `monkeypatch.setenv`, or `os.environ` in `conftest.py`. Tests should never spin up the scheduler.
- Add a unit test `tests/services/test_scheduler.py`:
  - Mocks two `ProviderConnection` rows.
  - Patches `sync_provider_connection` so one raises `Exception` and the other returns a `SyncResult`.
  - Asserts that both are attempted, the exception was logged, and the aggregate log includes `ok=1, failed=1`.

## Data model changes

None. `provider_connections.last_sync_at` already tracks per-connection state; the existing `sync_provider_connection` updates it.

## Failure & error semantics

| Scenario | Behavior |
|---|---|
| Gmail 401 / token cannot refresh for user X | Log and skip user X; other users still run. Next interval retries. |
| DB unavailable | Job's outer session-open raises; the scheduler swallows the exception (APScheduler default behavior); next interval retries. |
| Backend process restart | Scheduler is re-created; first job fires immediately on boot; subsequent runs at the configured interval. |
| Two containers running (unintended) | Both would sync in parallel. Out of scope — deployment is single-container. |

## Configuration matrix

| Env var | Default | Purpose |
|---|---|---|
| `SYNC_INTERVAL_HOURS` | `6` | Interval between full scans of all connections. |
| `SYNC_SCHEDULER_ENABLED` | `true` | When `false`, `lifespan` skips scheduler entirely. Use in tests and dev. |
| `GMAIL_SYNC_DEFAULT_LOOKBACK_DAYS` | `30` | Reused unchanged from the manual sync endpoint. |
| `GMAIL_SYNC_MAX_MESSAGES` | `200` | Reused unchanged. |

## Observability

- Per-connection log line on completion or failure with `user_id`, `connection_id`, `created`, `errors`.
- Aggregate log line per job run: total connections, ok, failed, duration.
- No new metrics endpoint; logs are sufficient for the single-user MVP.

## Rollout notes

- The first run fires immediately on `docker compose up backend`. If a token is broken, expect a single 401-shaped log within seconds of boot — not a regression.
- To temporarily disable in production: `SYNC_SCHEDULER_ENABLED=false` + `docker compose up -d backend`.
- To change cadence: `SYNC_INTERVAL_HOURS=<N>` + restart.

## File map

| Action | File | Purpose |
|---|---|---|
| Modify | `backend/pyproject.toml` | Add `apscheduler>=3.10` dependency |
| Modify | `backend/app/core/config.py` | Add `sync_interval_hours`, `sync_scheduler_enabled` |
| Create | `backend/app/services/scheduler.py` | `sync_all_users_job`, `build_scheduler` |
| Modify | `backend/app/main.py` | Wire `lifespan` that starts/stops the scheduler |
| Create | `backend/tests/services/__init__.py` | Package init |
| Create | `backend/tests/services/test_scheduler.py` | Unit test for `sync_all_users_job` |
| Modify | `backend/tests/conftest.py` (or create) | Disable scheduler in tests |
