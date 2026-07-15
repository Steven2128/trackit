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
from app.core.time_utils import last_completed_week_bounds
from app.db.session import AsyncSessionLocal
from app.models.notification_log import NotificationLog
from app.models.provider_connection import ProviderConnection, ProviderType
from app.models.push_token import PushToken
from app.models.user import User
from app.services.email_sender import send_email
from app.services.email_sync import sync_provider_connection
from app.services.push_alerts import collect_user_alerts
from app.services.push_sender import PushMessage, send_push_messages
from app.services.weekly_summary import build_weekly_summary, render_weekly_summary_email

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


async def send_weekly_summaries_job() -> None:
    """Email every user their spending digest for the week that just ended.

    Same isolation pattern as `sync_all_users_job`: one bad user (send
    failure, DB error) never stops the batch. Users with zero transactions
    in the window are skipped — no point emailing an empty summary.
    """
    started = time.monotonic()
    week_start_at, week_end_at, week_start_date, week_end_date = last_completed_week_bounds()

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User.id))
        user_ids = list(result.scalars())

    ok = 0
    skipped = 0
    failed = 0
    for user_id in user_ids:
        async with AsyncSessionLocal() as db:
            user = await db.get(User, user_id)
            if user is None:
                continue
            try:
                data = await build_weekly_summary(
                    db, user.id, week_start_at, week_end_at, week_start_date, week_end_date
                )
                if data.transaction_count == 0:
                    skipped += 1
                    continue
                subject, html = render_weekly_summary_email(data)
                await send_email(user.email, subject, html)
                ok += 1
            except Exception:  # noqa: BLE001 — one bad user must not stop the batch
                log.exception(
                    "send_weekly_summaries_job user_failed",
                    extra={"user_id": str(user_id)},
                )
                failed += 1

    duration_ms = int((time.monotonic() - started) * 1000)
    log.info(
        "send_weekly_summaries_job completed",
        extra={
            "total": len(user_ids),
            "ok": ok,
            "skipped": skipped,
            "failed": failed,
            "duration_ms": duration_ms,
        },
    )


async def send_push_alerts_job() -> None:
    """Daily push fan-out: budget 80/100% alerts, due dates <=3 days out and
    unusual-spending flags — the same data the app shows, pushed so the user
    hears about it without opening the app.

    Dedupe: each alert's `dedupe_key` is checked against (and then recorded
    in) `notification_logs`, so an alert fires once per period, not once per
    day. Same per-user failure isolation as the other jobs.
    """
    started = time.monotonic()
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(PushToken.user_id).distinct())
        user_ids = list(result.scalars())

    ok = 0
    skipped = 0
    failed = 0
    for user_id in user_ids:
        async with AsyncSessionLocal() as db:
            try:
                alerts = await collect_user_alerts(db, user_id)
                if alerts:
                    sent_result = await db.execute(
                        select(NotificationLog.dedupe_key).where(
                            NotificationLog.user_id == user_id,
                            NotificationLog.dedupe_key.in_(
                                [a.dedupe_key for a in alerts]
                            ),
                        )
                    )
                    already_sent = set(sent_result.scalars())
                    alerts = [a for a in alerts if a.dedupe_key not in already_sent]
                if not alerts:
                    skipped += 1
                    continue

                tokens_result = await db.execute(
                    select(PushToken).where(PushToken.user_id == user_id)
                )
                tokens = tokens_result.scalars().all()
                if not tokens:
                    skipped += 1
                    continue

                dead_tokens = await send_push_messages(
                    [
                        PushMessage(token=t.token, title=a.title, body=a.body)
                        for a in alerts
                        for t in tokens
                    ]
                )
                for token_row in tokens:
                    if token_row.token in dead_tokens:
                        await db.delete(token_row)
                for alert in alerts:
                    db.add(NotificationLog(user_id=user_id, dedupe_key=alert.dedupe_key))
                await db.commit()
                ok += 1
            except Exception:  # noqa: BLE001 — one bad user must not stop the batch
                log.exception(
                    "send_push_alerts_job user_failed", extra={"user_id": str(user_id)}
                )
                failed += 1

    duration_ms = int((time.monotonic() - started) * 1000)
    log.info(
        "send_push_alerts_job completed",
        extra={
            "total": len(user_ids),
            "ok": ok,
            "skipped": skipped,
            "failed": failed,
            "duration_ms": duration_ms,
        },
    )


def build_scheduler() -> AsyncIOScheduler:
    """Return an unstarted scheduler. Caller adds jobs and calls `.start()`."""
    return AsyncIOScheduler(timezone=timezone.utc)
