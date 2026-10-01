from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BudgetUpsert(BaseModel):
    monthly_limit: Decimal = Field(gt=0)


class BudgetRename(BaseModel):
    # Slug of the renamed custom category (mobile slugifies the display name).
    new_category: str = Field(pattern=r"^[a-z0-9_]{1,64}$")


class BudgetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    category: str
    monthly_limit: Decimal
    created_at: datetime


class BudgetStatusItem(BaseModel):
    category: str
    monthly_limit: Decimal
    spent: Decimal
    pct: Decimal
    status: str  # "ok" | "warning" | "exceeded"


class BudgetStatusResponse(BaseModel):
    month: str
    items: list[BudgetStatusItem]
