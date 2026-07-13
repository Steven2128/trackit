import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.core.time_utils import (
    current_month_local,
    last_completed_week_bounds,
    month_bounds,
    user_tz,
)


def test_user_tz_returns_zoneinfo():
    tz = user_tz()
    assert isinstance(tz, ZoneInfo)


def test_user_tz_is_bogota():
    tz = user_tz()
    assert str(tz) == "America/Bogota"


def test_current_month_local_matches_yyyy_mm():
    result = current_month_local()
    assert re.match(r"^\d{4}-\d{2}$", result)


def test_month_bounds_start_is_first_of_month():
    start, _ = month_bounds("2026-06")
    assert start.year == 2026
    assert start.month == 6
    assert start.day == 1


def test_month_bounds_end_is_first_of_next_month():
    _, end = month_bounds("2026-06")
    assert end.year == 2026
    assert end.month == 7
    assert end.day == 1


def test_month_bounds_december_wraps_to_january():
    _, end = month_bounds("2025-12")
    assert end.year == 2026
    assert end.month == 1
    assert end.day == 1


def test_month_bounds_are_timezone_aware():
    start, end = month_bounds("2026-06")
    assert start.tzinfo is not None
    assert end.tzinfo is not None


def test_month_bounds_start_less_than_end():
    start, end = month_bounds("2026-01")
    assert start < end


def test_month_bounds_invalid_raises():
    with pytest.raises((ValueError, TypeError)):
        month_bounds("not-valid")


def test_last_completed_week_bounds_start_is_monday():
    reference = datetime(2026, 7, 15, 10, 30, tzinfo=user_tz())  # any weekday
    start, _, _, _ = last_completed_week_bounds(reference)
    assert start.weekday() == 0


def test_last_completed_week_bounds_end_is_monday_seven_days_after_start():
    reference = datetime(2026, 7, 15, 10, 30, tzinfo=user_tz())
    start, end, _, _ = last_completed_week_bounds(reference)
    assert end.weekday() == 0
    assert end - start == timedelta(days=7)


def test_last_completed_week_bounds_excludes_current_week():
    reference = datetime(2026, 7, 15, 10, 30, tzinfo=user_tz())
    _, end, _, _ = last_completed_week_bounds(reference)
    assert reference >= end


def test_last_completed_week_bounds_week_end_date_is_sunday():
    reference = datetime(2026, 7, 15, 10, 30, tzinfo=user_tz())
    _, _, week_start_date, week_end_date = last_completed_week_bounds(reference)
    assert week_end_date.weekday() == 6
    assert (week_end_date - week_start_date).days == 6


def test_last_completed_week_bounds_are_timezone_aware():
    reference = datetime(2026, 7, 15, 10, 30, tzinfo=user_tz())
    start, end, _, _ = last_completed_week_bounds(reference)
    assert start.tzinfo is not None
    assert end.tzinfo is not None


def test_last_completed_week_bounds_defaults_to_now():
    start, end, _, _ = last_completed_week_bounds()
    assert start.tzinfo is not None
    assert end - start == timedelta(days=7)
