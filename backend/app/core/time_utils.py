# app/core/time_utils.py
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.sql import ColumnElement

from app.core.config import settings
from app.models.transaction import Transaction


def user_tz() -> ZoneInfo:
    return ZoneInfo(settings.user_timezone)


def current_month_local() -> str:
    now = datetime.now(tz=user_tz())
    return f"{now.year:04d}-{now.month:02d}"


def month_bounds(month: str) -> tuple[datetime, datetime]:
    """(start_inclusive, end_exclusive) as tz-aware datetimes for a YYYY-MM month."""
    year_str, month_str = month.split("-")
    year, month_num = int(year_str), int(month_str)
    tz = user_tz()
    start_local = datetime(year, month_num, 1, tzinfo=tz)
    if month_num == 12:
        end_local = datetime(year + 1, 1, 1, tzinfo=tz)
    else:
        end_local = datetime(year, month_num + 1, 1, tzinfo=tz)
    return start_local, end_local


def month_filter(month: str | None) -> list[ColumnElement]:
    """SQLAlchemy WHERE clauses for a YYYY-MM month.
    Raises HTTP 400 if month format is invalid. Uses current month if None."""
    if month is None:
        month = current_month_local()
    try:
        start, end = month_bounds(month)
    except (ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_month_format",
        ) from exc
    return [
        Transaction.occurred_at >= start,
        Transaction.occurred_at < end,
    ]


def not_in_excluded(column: ColumnElement, excluded: tuple[str, ...]) -> ColumnElement:
    """`category` may be NULL — `NOT IN` returns NULL for NULL inputs.
    Use IS NULL OR NOT IN so NULLs pass through."""
    return column.is_(None) | column.notin_(excluded)
