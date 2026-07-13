import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, computed_field


class SavingsGoalBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    target_amount: Decimal = Field(..., gt=0)
    current_amount: Decimal = Field(default=Decimal("0"), ge=0)
    target_date: date | None = None


class SavingsGoalCreate(SavingsGoalBase):
    pass


class SavingsGoalUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    target_amount: Decimal | None = Field(default=None, gt=0)
    current_amount: Decimal | None = Field(default=None, ge=0)
    target_date: date | None = None


class SavingsGoalOut(SavingsGoalBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def pct(self) -> int:
        if self.target_amount <= 0:
            return 0
        return min(100, int(self.current_amount * 100 / self.target_amount))
