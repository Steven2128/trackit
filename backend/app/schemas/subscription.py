from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class SubscriptionOut(BaseModel):
    merchant: str
    category: str | None
    average_amount: Decimal
    frequency: str  # "weekly" | "biweekly" | "monthly" | "yearly"
    occurrences: int
    last_occurred_at: datetime
    next_expected_at: datetime
