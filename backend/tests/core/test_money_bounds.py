from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.account import CashExpenseIn
from app.schemas.budget import BudgetUpsert
from app.schemas.debt import DebtCreate
from app.schemas.plan import PlannedPaymentCreate
from app.schemas.savings_goal import SavingsGoalCreate


@pytest.mark.parametrize(
    "build",
    [
        lambda v: BudgetUpsert(monthly_limit=v),
        lambda v: CashExpenseIn(amount=v, merchant="x"),
        lambda v: DebtCreate(bank_name="x", total_amount=Decimal(1), minimum_payment=v),
    ],
)
def test_numeric_12_2_fields_reject_overflow(build) -> None:
    build(Decimal("9999999999.99"))
    # 120000120000 is what a double-typed "120000" produces.
    with pytest.raises(ValidationError):
        build(Decimal("120000120000"))


@pytest.mark.parametrize(
    "build",
    [
        lambda v: SavingsGoalCreate(name="x", target_amount=v),
        lambda v: PlannedPaymentCreate(name="x", amount=v),
        lambda v: DebtCreate(bank_name="x", total_amount=v),
    ],
)
def test_numeric_14_2_fields_reject_overflow(build) -> None:
    build(Decimal("999999999999.99"))
    with pytest.raises(ValidationError):
        build(Decimal("1000000000000"))


def test_interest_rate_bounds() -> None:
    DebtCreate(bank_name="x", total_amount=Decimal(1), interest_rate=Decimal("28.5"))
    with pytest.raises(ValidationError):
        DebtCreate(bank_name="x", total_amount=Decimal(1), interest_rate=Decimal("1000"))
