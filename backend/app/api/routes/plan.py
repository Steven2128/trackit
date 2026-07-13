"""Monthly plan: income calendar, planned payments (apartados/reminders)
and projected cash flow.

Cash flow is computed on the fly like /dashboard — no persisted state.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.time_utils import user_tz
from app.models.income_source import IncomeSource
from app.models.planned_payment import PlannedPayment
from app.schemas.plan import (
    CashFlowResponse,
    IncomeSourceCreate,
    IncomeSourceOut,
    IncomeSourceUpdate,
    PlannedPaymentCreate,
    PlannedPaymentOut,
    PlannedPaymentUpdate,
    UpcomingPaymentOut,
)
from app.services.cash_flow import IncomeLike, PaymentLike, compute_cash_flow

router = APIRouter(tags=["plan"])


# --- Income sources ---


@router.get("/income-sources", response_model=list[IncomeSourceOut])
async def list_income_sources(
    current_user: CurrentUser, db: DbSession
) -> list[IncomeSourceOut]:
    result = await db.execute(
        select(IncomeSource)
        .where(IncomeSource.user_id == current_user.id)
        .order_by(IncomeSource.expected_day)
    )
    return [IncomeSourceOut.model_validate(i) for i in result.scalars().all()]


@router.post(
    "/income-sources", response_model=IncomeSourceOut, status_code=status.HTTP_201_CREATED
)
async def create_income_source(
    payload: IncomeSourceCreate, current_user: CurrentUser, db: DbSession
) -> IncomeSourceOut:
    income = IncomeSource(user_id=current_user.id, **payload.model_dump())
    db.add(income)
    await db.commit()
    await db.refresh(income)
    return IncomeSourceOut.model_validate(income)


@router.patch("/income-sources/{income_id}", response_model=IncomeSourceOut)
async def update_income_source(
    income_id: uuid.UUID,
    payload: IncomeSourceUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> IncomeSourceOut:
    income = await _get_own(IncomeSource, income_id, current_user.id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(income, field, value)
    await db.commit()
    await db.refresh(income)
    return IncomeSourceOut.model_validate(income)


@router.delete("/income-sources/{income_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_income_source(
    income_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> None:
    income = await _get_own(IncomeSource, income_id, current_user.id, db)
    await db.delete(income)
    await db.commit()


# --- Planned payments ---


@router.get("/planned-payments", response_model=list[PlannedPaymentOut])
async def list_planned_payments(
    current_user: CurrentUser, db: DbSession
) -> list[PlannedPaymentOut]:
    result = await db.execute(
        select(PlannedPayment)
        .where(PlannedPayment.user_id == current_user.id)
        .order_by(PlannedPayment.due_day.nulls_last(), PlannedPayment.name)
    )
    return [PlannedPaymentOut.model_validate(p) for p in result.scalars().all()]


@router.post(
    "/planned-payments",
    response_model=PlannedPaymentOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_planned_payment(
    payload: PlannedPaymentCreate, current_user: CurrentUser, db: DbSession
) -> PlannedPaymentOut:
    payment = PlannedPayment(user_id=current_user.id, **payload.model_dump())
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    return PlannedPaymentOut.model_validate(payment)


@router.patch("/planned-payments/{payment_id}", response_model=PlannedPaymentOut)
async def update_planned_payment(
    payment_id: uuid.UUID,
    payload: PlannedPaymentUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> PlannedPaymentOut:
    payment = await _get_own(PlannedPayment, payment_id, current_user.id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(payment, field, value)
    await db.commit()
    await db.refresh(payment)
    return PlannedPaymentOut.model_validate(payment)


@router.delete("/planned-payments/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_planned_payment(
    payment_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> None:
    payment = await _get_own(PlannedPayment, payment_id, current_user.id, db)
    await db.delete(payment)
    await db.commit()


# --- Cash flow ---


@router.get("/cashflow", response_model=CashFlowResponse)
async def cash_flow(current_user: CurrentUser, db: DbSession) -> CashFlowResponse:
    incomes_result = await db.execute(
        select(IncomeSource).where(IncomeSource.user_id == current_user.id)
    )
    payments_result = await db.execute(
        select(PlannedPayment).where(PlannedPayment.user_id == current_user.id)
    )

    incomes = [
        IncomeLike(name=i.name, amount=i.amount, expected_day=i.expected_day)
        for i in incomes_result.scalars().all()
    ]
    payments = [
        PaymentLike(
            name=p.name,
            amount=p.amount,
            due_day=p.due_day,
            grace_days=p.grace_days,
            is_debt_payment=p.is_debt_payment,
        )
        for p in payments_result.scalars().all()
    ]

    today = datetime.now(user_tz()).date()
    result = compute_cash_flow(incomes, payments, today)

    def _out(items) -> list[UpcomingPaymentOut]:
        return [
            UpcomingPaymentOut(
                name=u.name,
                amount=u.amount,
                deadline=u.deadline,
                days_left=u.days_left,
                is_debt_payment=u.is_debt_payment,
            )
            for u in items
        ]

    return CashFlowResponse(
        monthly_income=result.monthly_income,
        monthly_committed=result.monthly_committed,
        available=result.available,
        next_income_date=result.next_income_date,
        next_income_name=result.next_income_name,
        next_income_amount=result.next_income_amount,
        upcoming=_out(result.upcoming),
        checklist=_out(result.checklist),
    )


async def _get_own(model, obj_id: uuid.UUID, user_id: uuid.UUID, db: DbSession):
    result = await db.execute(
        select(model).where(model.id == obj_id, model.user_id == user_id)
    )
    obj = result.scalar_one_or_none()
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
    return obj
