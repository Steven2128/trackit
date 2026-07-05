# Dashboard Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `GET /dashboard` endpoint returning 6-month spending trend, current-month snapshot, and debt totals.

**Architecture:** Three async queries run concurrently via `asyncio.gather`. Time helpers extracted from `transactions.py` into a shared `time_utils.py` module. Route uses existing `Transaction` and `Debt` models — no migrations.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Pydantic v2, asyncpg, pytest + pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-06-30-dashboard-backend-design.md`

---

## File Map

| Action | File | Purpose |
|--------|------|---------|
| Create | `app/core/time_utils.py` | Shared time helpers: `user_tz`, `current_month_local`, `month_bounds`, `month_filter`, `not_in_excluded` |
| Create | `app/schemas/dashboard.py` | Pydantic response schemas for dashboard |
| Create | `app/api/routes/dashboard.py` | `GET /dashboard` router with 3 concurrent queries |
| Create | `tests/core/__init__.py` | Package init |
| Create | `tests/core/test_time_utils.py` | Unit tests for time helpers |
| Modify | `app/api/routes/transactions.py` | Remove local helpers; import from `time_utils` |
| Modify | `app/main.py` | Register `dashboard.router` |

---

## Task 1: Write failing tests for time_utils

**Files:**
- Create: `tests/core/__init__.py`
- Create: `tests/core/test_time_utils.py`

- [x] **Step 1: Create package init**

```python
# tests/core/__init__.py
# (empty)
```

- [x] **Step 2: Write the failing tests**

```python
# tests/core/test_time_utils.py
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
```

- [x] **Step 3: Run tests to verify they fail**

```
cd backend
docker compose run --rm backend pytest tests/core/test_time_utils.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.core.time_utils'`

---

## Task 2: Create `app/core/time_utils.py` (make tests pass)

**Files:**
- Create: `app/core/time_utils.py`

- [x] **Step 1: Write the module**

```python
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
    year, month_num = int(month[:4]), int(month[5:])
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
```

- [x] **Step 2: Run tests to verify they pass**

```
docker compose run --rm backend pytest tests/core/test_time_utils.py -v
```

Expected: all 9 tests PASS

- [x] **Step 3: Commit**

```bash
git add app/core/time_utils.py tests/core/__init__.py tests/core/test_time_utils.py
git commit -m "feat: add time_utils with month helpers and not_in_excluded"
```

---

## Task 3: Refactor `transactions.py` to import from time_utils

**Files:**
- Modify: `app/api/routes/transactions.py`

Current state: `transactions.py` defines `_user_tz`, `_current_month_local`, `_month_filter`, `_not_in_excluded` locally (lines 132–177). After this task they come from `time_utils`.

Note: Line 79 has `month_filter = _month_filter(resolved_month)` — a local variable that would shadow the imported function. Rename to `month_clauses`.

- [x] **Step 1: Apply the changes**

Remove the module docstring imports section and replace imports at the top of the file. Old header:

```python
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.sql import ColumnElement

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.models.transaction import Transaction, TransactionType
from app.schemas.transaction import (
    CategorySummaryItem,
    TransactionListResponse,
    TransactionOut,
    TransactionSummary,
)
```

New header (remove `datetime`, `ZoneInfo`, `HTTPException`, `status`, `settings`, `ColumnElement`; add `time_utils` imports):

```python
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Query
from sqlalchemy import func, select
from sqlalchemy.sql import ColumnElement

from app.api.deps import CurrentUser, DbSession
from app.core.time_utils import current_month_local, month_filter, not_in_excluded
from app.models.transaction import Transaction, TransactionType
from app.schemas.transaction import (
    CategorySummaryItem,
    TransactionListResponse,
    TransactionOut,
    TransactionSummary,
)
```

- [x] **Step 2: Fix the local variable name collision in `transactions_summary`**

Old (line 78–80):
```python
    resolved_month = month or _current_month_local()
    month_filter = _month_filter(resolved_month)
    base_filter = [Transaction.user_id == current_user.id, *month_filter]
```

New:
```python
    resolved_month = month or current_month_local()
    month_clauses = month_filter(resolved_month)
    base_filter = [Transaction.user_id == current_user.id, *month_clauses]
```

- [x] **Step 3: Fix `list_transactions` call**

Old (line 49):
```python
    filters.extend(_month_filter(month))
```

New:
```python
    filters.extend(month_filter(month))
```

- [x] **Step 4: Replace `_not_in_excluded` calls (3 occurrences)**

Old:
```python
_not_in_excluded(Transaction.category, EXCLUDED_FROM_SPENT_CATEGORIES)
```

New:
```python
not_in_excluded(Transaction.category, EXCLUDED_FROM_SPENT_CATEGORIES)
```

Apply same rename for `EXCLUDED_FROM_RECEIVED_CATEGORIES` call (line 95).

- [x] **Step 5: Delete the now-unused local definitions (lines 132–177)**

Delete these functions from the end of the file:
- `_not_in_excluded` (line 132)
- `_sum_amount` stays (still local to transactions.py)
- `_month_filter` (line 146)
- `_current_month_local` (line 170)
- `_user_tz` (line 175)

- [x] **Step 6: Run existing tests to verify no regression**

```
docker compose run --rm backend pytest tests/ -v
```

Expected: all existing parser and categorizer tests PASS

- [x] **Step 7: Commit**

```bash
git add app/api/routes/transactions.py
git commit -m "refactor: import time helpers from time_utils in transactions router"
```

---

## Task 4: Create `app/schemas/dashboard.py`

**Files:**
- Create: `app/schemas/dashboard.py`

No tests needed — pure Pydantic models; correctness verified by the route's response_model validation at runtime.

- [x] **Step 1: Write the schemas**

```python
# app/schemas/dashboard.py
from decimal import Decimal

from pydantic import BaseModel


class MonthCategoryItem(BaseModel):
    category: str | None
    total: Decimal
    count: int


class MonthTrendEntry(BaseModel):
    month: str
    total_spent: Decimal
    by_category: list[MonthCategoryItem]


class CurrentMonthSnapshot(BaseModel):
    month: str
    total_spent: Decimal
    by_category: list[MonthCategoryItem]
    transaction_count: int


class DebtSnapshot(BaseModel):
    total_debt: Decimal
    total_minimum_payment: Decimal
    debt_count: int


class DashboardResponse(BaseModel):
    monthly_trend: list[MonthTrendEntry]
    current_month: CurrentMonthSnapshot
    debts: DebtSnapshot
```

- [x] **Step 2: Commit**

```bash
git add app/schemas/dashboard.py
git commit -m "feat: add dashboard response schemas"
```

---

## Task 5: Create `app/api/routes/dashboard.py`

**Files:**
- Create: `app/api/routes/dashboard.py`

- [x] **Step 1: Write the route**

```python
# app/api/routes/dashboard.py
"""GET /dashboard — consolidated view: 6-month trend, current month, debts.

Three queries run concurrently. Month windowing uses settings.user_timezone
(default America/Bogota) — same rule as GET /transactions/summary.
Spending excludes transfer and cash_withdrawal categories.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.core.time_utils import current_month_local, month_bounds, not_in_excluded
from app.models.debt import Debt
from app.models.transaction import Transaction, TransactionType
from app.schemas.dashboard import (
    CurrentMonthSnapshot,
    DashboardResponse,
    DebtSnapshot,
    MonthCategoryItem,
    MonthTrendEntry,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_EXCLUDED = ("transfer", "cash_withdrawal")


@router.get("", response_model=DashboardResponse)
async def get_dashboard(current_user: CurrentUser, db: DbSession) -> DashboardResponse:
    current_month = current_month_local()
    trend_months = _six_months(current_month)
    trend_start, _ = month_bounds(trend_months[0])

    trend_rows, tx_count, debt_row = await asyncio.gather(
        _fetch_trend(db, current_user.id, trend_start),
        _fetch_count(db, current_user.id, current_month),
        _fetch_debts(db, current_user.id),
    )

    monthly_trend = _build_trend(trend_rows, trend_months)
    last = monthly_trend[-1]

    return DashboardResponse(
        monthly_trend=monthly_trend,
        current_month=CurrentMonthSnapshot(
            month=last.month,
            total_spent=last.total_spent,
            by_category=last.by_category,
            transaction_count=tx_count,
        ),
        debts=DebtSnapshot(
            total_debt=Decimal(str(debt_row.total_debt)),
            total_minimum_payment=Decimal(str(debt_row.total_min)),
            debt_count=debt_row.debt_count,
        ),
    )


async def _fetch_trend(db, user_id, trend_start: datetime):
    tz_str = settings.user_timezone
    local_ts = func.timezone(tz_str, func.timezone("UTC", Transaction.occurred_at))
    month_col = func.date_trunc("month", local_ts).label("month")

    result = await db.execute(
        select(
            month_col,
            Transaction.category,
            func.sum(Transaction.amount).label("total"),
            func.count().label("cnt"),
        )
        .where(
            Transaction.user_id == user_id,
            Transaction.transaction_type == TransactionType.debit,
            not_in_excluded(Transaction.category, _EXCLUDED),
            Transaction.occurred_at >= trend_start,
        )
        .group_by(month_col, Transaction.category)
        .order_by(month_col)
    )
    return result.all()


async def _fetch_count(db, user_id, current_month: str) -> int:
    month_start, month_end = month_bounds(current_month)
    result = await db.execute(
        select(func.count()).where(
            Transaction.user_id == user_id,
            Transaction.occurred_at >= month_start,
            Transaction.occurred_at < month_end,
        )
    )
    return result.scalar_one()


async def _fetch_debts(db, user_id):
    result = await db.execute(
        select(
            func.count().label("debt_count"),
            func.coalesce(func.sum(Debt.total_amount), 0).label("total_debt"),
            func.coalesce(func.sum(Debt.minimum_payment), 0).label("total_min"),
        ).where(Debt.user_id == user_id)
    )
    return result.one()


def _six_months(current: str) -> list[str]:
    """Returns 6 YYYY-MM strings: [5-months-ago, ..., current], oldest first."""
    y, m = int(current[:4]), int(current[5:])
    result = []
    for i in range(5, -1, -1):
        mi = m - i
        yi = y
        while mi <= 0:
            mi += 12
            yi -= 1
        result.append(f"{yi:04d}-{mi:02d}")
    return result


def _build_trend(rows, months: list[str]) -> list[MonthTrendEntry]:
    raw: dict[str, list[MonthCategoryItem]] = defaultdict(list)
    for row in rows:
        month_dt: datetime = row.month
        month_str = f"{month_dt.year:04d}-{month_dt.month:02d}"
        raw[month_str].append(
            MonthCategoryItem(
                category=row.category,
                total=Decimal(str(row.total)),
                count=row.cnt,
            )
        )

    trend = []
    for month_str in months:
        items = raw.get(month_str, [])
        trend.append(
            MonthTrendEntry(
                month=month_str,
                total_spent=sum((item.total for item in items), Decimal("0")),
                by_category=items,
            )
        )
    return trend
```

- [x] **Step 2: Commit**

```bash
git add app/api/routes/dashboard.py
git commit -m "feat: add GET /dashboard endpoint with trend, snapshot, and debt queries"
```

---

## Task 6: Register router in `app/main.py`

**Files:**
- Modify: `app/main.py`

- [x] **Step 1: Add import and include_router**

Old `app/main.py`:
```python
from app.api.routes import auth, debts, gmail, transactions
```

New:
```python
from app.api.routes import auth, dashboard, debts, gmail, transactions
```

Add after `app.include_router(transactions.router)`:
```python
    app.include_router(dashboard.router)
```

Full updated `create_app` function:
```python
def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="TrackIt API", version="0.1.0")

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
```

- [x] **Step 2: Run all tests**

```
docker compose run --rm backend pytest tests/ -v
```

Expected: all tests PASS

- [x] **Step 3: Start the backend and smoke-test the endpoint**

```bash
docker compose up -d backend
curl -s -H "Authorization: Bearer <your_token>" http://localhost:8000/dashboard | python -m json.tool
```

Expected: JSON with `monthly_trend` (6 entries), `current_month`, `debts` keys.

Also verify the OpenAPI docs show the new endpoint:
```
http://localhost:8000/docs
```

- [x] **Step 4: Commit**

```bash
git add app/main.py
git commit -m "feat: register dashboard router in main app"
```

---

## Self-Review Against Spec

**Spec coverage check:**

| Spec requirement | Covered by |
|-----------------|------------|
| `monthly_trend` has exactly 6 entries, oldest→newest | `_six_months` + `_build_trend` in Task 5 |
| Missing months appear with `total_spent: 0`, `by_category: []` | `_build_trend` fills from `months` list, defaults to `[]` |
| `current_month` derived from trend[5] + separate count query | Task 5: `last = monthly_trend[-1]` + `_fetch_count` |
| Spending excludes `transfer`, `cash_withdrawal` | `_EXCLUDED` tuple + `not_in_excluded` in trend query |
| NULL category passes through | `not_in_excluded` uses `IS NULL OR NOT IN` |
| No debts → `debt_count: 0`, amounts `0` | `COALESCE(..., 0)` in `_fetch_debts` |
| DB error → HTTP 500 | Propagates naturally from async SQLAlchemy |
| Unauthenticated → HTTP 401 | `CurrentUser` dependency in `get_dashboard` |
| 3 queries concurrent via `asyncio.gather` | Task 5 `get_dashboard` |
| Schemas match spec exactly | Task 4 |
| `time_utils` extracted from transactions | Tasks 1–3 |
| Router registered in main.py | Task 6 |

**Placeholder scan:** None found.

**Type consistency:** `MonthCategoryItem`, `MonthTrendEntry`, `CurrentMonthSnapshot`, `DebtSnapshot`, `DashboardResponse` defined in Task 4 and used identically in Task 5. `month_bounds`, `current_month_local`, `not_in_excluded` defined in Task 2 and used in Tasks 3 and 5.
