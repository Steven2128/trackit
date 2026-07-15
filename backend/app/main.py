import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    auth,
    budgets,
    dashboard,
    debts,
    gmail,
    goals,
    insights,
    notifications,
    plan,
    subscriptions,
    transactions,
)
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.time_utils import user_tz
from app.services.scheduler import (
    build_scheduler,
    send_push_alerts_job,
    send_weekly_summaries_job,
    sync_all_users_job,
)

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
        if settings.weekly_summary_enabled:
            scheduler.add_job(
                send_weekly_summaries_job,
                CronTrigger(
                    day_of_week=settings.weekly_summary_day_of_week,
                    hour=settings.weekly_summary_hour,
                    timezone=user_tz(),
                ),
                id="weekly_summary",
                replace_existing=True,
            )
            log.info(
                "weekly_summary_scheduled",
                extra={
                    "day_of_week": settings.weekly_summary_day_of_week,
                    "hour": settings.weekly_summary_hour,
                },
            )
        if settings.push_alerts_enabled:
            scheduler.add_job(
                send_push_alerts_job,
                CronTrigger(hour=settings.push_alerts_hour, timezone=user_tz()),
                id="push_alerts",
                replace_existing=True,
            )
            log.info(
                "push_alerts_scheduled", extra={"hour": settings.push_alerts_hour}
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
    app.include_router(budgets.router)
    app.include_router(subscriptions.router)
    app.include_router(goals.router)
    app.include_router(plan.router)
    app.include_router(insights.router)
    app.include_router(notifications.router)

    return app


app = create_app()
