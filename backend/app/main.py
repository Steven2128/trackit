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
