"""External cron triggers for the scheduled jobs.

On Render's free tier the instance sleeps after ~15 min without traffic, so
the in-process APScheduler (`app/main.py` lifespan) never fires reliably.
In production `SYNC_SCHEDULER_ENABLED=false` and a GitHub Actions cron
(`.github/workflows/cron.yml`) calls these endpoints instead — the request
itself wakes the instance. Each job runs inline so the caller's logs show
whether it finished.

Auth: `Authorization: Bearer <CRON_SECRET>`. With no secret configured the
endpoints return 404, so they don't exist in local dev by accident.
"""

from __future__ import annotations

import hmac
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status

from app.core.config import settings
from app.services.scheduler import (
    send_push_alerts_job,
    send_weekly_summaries_job,
    sync_all_users_job,
)

router = APIRouter(prefix="/internal/cron", tags=["cron"], include_in_schema=False)

_JOBS: dict[str, Callable[[], Awaitable[None]]] = {
    "gmail-sync": sync_all_users_job,
    "weekly-summary": send_weekly_summaries_job,
    "push-alerts": send_push_alerts_job,
}


def _check_secret(authorization: str | None) -> None:
    if not settings.cron_secret:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    expected = f"Bearer {settings.cron_secret}"
    if not authorization or not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


@router.post("/{job}")
async def run_job(
    job: str,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, str]:
    _check_secret(authorization)
    runner = _JOBS.get(job)
    if runner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown job")
    await runner()
    return {"job": job, "status": "done"}
