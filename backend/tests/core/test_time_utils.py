import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from app.core.time_utils import current_month_local, month_bounds, user_tz


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
