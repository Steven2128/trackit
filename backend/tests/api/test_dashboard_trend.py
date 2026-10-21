from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

from app.api.routes.dashboard import _build_trend


def _row(month: int, total: str, category: str | None = None, cnt: int = 1) -> SimpleNamespace:
    return SimpleNamespace(month=datetime(2026, month, 1), category=category, total=total, cnt=cnt)


def test_received_lands_in_its_month_and_missing_months_are_zero() -> None:
    trend = _build_trend(
        [_row(9, "1000", "food"), _row(10, "250", "food")],
        ["2026-09", "2026-10", "2026-11"],
        [_row(10, "2273096")],
    )

    assert [t.total_received for t in trend] == [Decimal("0"), Decimal("2273096"), Decimal("0")]
    assert [t.total_spent for t in trend] == [Decimal("1000"), Decimal("250"), Decimal("0")]
