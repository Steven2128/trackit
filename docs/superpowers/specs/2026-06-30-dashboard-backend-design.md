# Dashboard Backend — Design Spec

**Date:** 2026-06-30  
**Status:** Approved  
**Scope:** Sprint 4 — `GET /dashboard` endpoint

---

## Summary

Single authenticated endpoint that returns everything the mobile Dashboard screen needs: a 6-month spending trend by category, a current-month snapshot, and a consolidated debt summary. No new DB migrations required.

---

## Architecture

### New files

| File | Purpose |
|------|---------|
| `app/core/time_utils.py` | Shared time helpers: `month_filter`, `current_month_local`, `user_tz` |
| `app/api/routes/dashboard.py` | `GET /dashboard` router |
| `app/schemas/dashboard.py` | Response schemas |

### Modified files

| File | Change |
|------|--------|
| `app/api/routes/transactions.py` | Import time helpers from `time_utils` instead of defining locally |
| `app/main.py` | Register `dashboard.router` |

No new Alembic migrations — reads existing `transactions` and `debts` tables.

---

## API Contract

```
GET /dashboard
Authorization: Bearer <access_token>
```

### Response (200 OK)

```json
{
  "monthly_trend": [
    {
      "month": "2026-01",
      "total_spent": 1250000.00,
      "by_category": [
        {"category": "food", "total": 450000.00, "count": 12},
        {"category": "transport", "total": 180000.00, "count": 8}
      ]
    }
  ],
  "current_month": {
    "month": "2026-06",
    "total_spent": 980000.00,
    "by_category": [
      {"category": "food", "total": 320000.00, "count": 9}
    ],
    "transaction_count": 34
  },
  "debts": {
    "total_debt": 15000000.00,
    "total_minimum_payment": 850000.00,
    "debt_count": 3
  }
}
```

### Contract rules

- `monthly_trend` always has exactly 6 entries ordered chronologically (oldest → newest). The 6th entry is always the current month.
- If a month has no transactions, it appears with `total_spent: 0.00` and `by_category: []`.
- `current_month` is derived from the same data pass as `monthly_trend[5]`, plus `transaction_count` from a separate count query.
- Spending excludes `transfer` and `cash_withdrawal` categories (same rule as `GET /transactions/summary`).
- `NULL` category transactions are included in spending (passed through the exclusion filter, same as existing behavior).
- All amounts reflect whatever currency is stored in the DB (COP for Itaú Colombia).
- If the user has no debts: `debt_count: 0`, `total_debt: 0`, `total_minimum_payment: 0`.

---

## Data Flow

Three async queries run concurrently via `asyncio.gather`:

### Query 1 — 6-month trend

Single SQL query using `DATE_TRUNC('month', occurred_at AT TIME ZONE 'UTC' AT TIME ZONE user_tz)` grouped by `(month, category)`. Filters:

- `user_id = current_user.id`
- `transaction_type = 'debit'`
- `category NOT IN ('transfer', 'cash_withdrawal') OR category IS NULL`
- `occurred_at >= start of the month that is 5 months before the current month (local time, converted to UTC)` — gives 6 entries total: 5 prior months + current month

Post-processed in Python: build a dict keyed by month string, fill missing months with zero entries, produce the sorted 6-entry list.

### Query 2 — Current month transaction count

```sql
SELECT COUNT(*) FROM transactions
WHERE user_id = ? AND occurred_at >= month_start AND occurred_at < month_end
```

Used to populate `current_month.transaction_count`. The spending total and by-category breakdown for current month come from Query 1's last entry (no extra query).

### Query 3 — Debt snapshot

```sql
SELECT COUNT(*), COALESCE(SUM(total_amount), 0), COALESCE(SUM(minimum_payment), 0)
FROM debts WHERE user_id = ?
```

---

## Error Handling

| Scenario | Behavior |
|----------|---------|
| No transactions | Trend with 6 zero-months, `current_month.total_spent: 0` |
| No debts | `debt_count: 0`, amounts `0` |
| DB error | Propagates as HTTP 500 (repo pattern) |
| Unauthenticated | HTTP 401 via `CurrentUser` dependency |

No input parameters → no input validation needed.

---

## Schemas (`app/schemas/dashboard.py`)

```python
class MonthCategoryItem(BaseModel):
    category: str | None
    total: Decimal
    count: int

class MonthTrendEntry(BaseModel):
    month: str          # "YYYY-MM"
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

---

## Out of scope

- Caching / TTL (not needed at personal-app scale)
- Income trend (only spending requested)
- Per-debt list (only consolidated totals)
- Transfer matcher integration (separate Sprint 4 item)
