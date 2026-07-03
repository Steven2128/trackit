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
from datetime import timezone

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
