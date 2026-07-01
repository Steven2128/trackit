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
