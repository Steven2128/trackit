"""Recurring-charge detection — computed on read, no stored state (same
pattern as `GET /dashboard`). See `app/services/subscription_detector.py`
for the detection core."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.time_utils import not_in_excluded
from app.models.transaction import Transaction, TransactionType
from app.schemas.subscription import SubscriptionOut
from app.services.subscription_detector import TransactionLike, detect_subscriptions

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])

# Transfers between own accounts and cash withdrawals aren't recurring
# spending — same exclusion as /transactions/summary.
EXCLUDED_CATEGORIES = ("transfer", "cash_withdrawal", "debt_payment")


@router.get("", response_model=list[SubscriptionOut])
async def list_subscriptions(
    current_user: CurrentUser,
    db: DbSession,
    lookback_days: int = Query(default=180, ge=30, le=730),
) -> list[SubscriptionOut]:
    window_start = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    result = await db.execute(
        select(Transaction).where(
            Transaction.user_id == current_user.id,
            Transaction.transaction_type == TransactionType.debit,
            Transaction.occurred_at >= window_start,
            not_in_excluded(Transaction.category, EXCLUDED_CATEGORIES),
        )
    )

    transactions = [
        TransactionLike(
            merchant=t.merchant,
            amount=t.amount,
            category=t.category,
            occurred_at=t.occurred_at,
        )
        for t in result.scalars().all()
    ]

    detected = detect_subscriptions(transactions)
    return [SubscriptionOut(**d.__dict__) for d in detected]
