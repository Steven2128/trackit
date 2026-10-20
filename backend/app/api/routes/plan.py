"""Monthly plan: income calendar, planned payments (apartados/reminders)
and projected cash flow.

Cash flow is computed on the fly like /dashboard — no persisted state.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.time_utils import current_month_local, user_tz
from app.models.debt import Debt
from app.models.income_source import IncomeSource
from app.models.planned_payment import PlannedPayment
from app.models.transaction import Transaction, TransactionType
from app.schemas.plan import (
    CashFlowResponse,
    CashPositionResponse,
    IncomeSourceCreate,
    IncomeSourceOut,
    IncomeSourceUpdate,
    PlannedPaymentCreate,
    PlannedPaymentOut,
    PlannedPaymentUpdate,
    PositionDeficitOut,
    PositionLineOut,
    PositionWindowOut,
    UpcomingPaymentOut,
)
from app.services.cash_flow import IncomeLike, PaymentLike, compute_cash_flow
from app.services.cash_position import compute_position
from app.services.cash_position_sources import (
    NOTES,
    STATEMENT_WINDOW_DAYS,
    Credit,
    DebtPayment,
    build_inputs,
    default_horizon,
)
from app.services.net_worth import net_worth

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
    this_month = current_month_local()
    payments = [
        PaymentLike(
            name=p.name,
            amount=p.amount,
            due_day=p.due_day,
            grace_days=p.grace_days,
            is_debt_payment=p.is_debt_payment,
            id=p.id,
            # Check-off is per local month; an old paid_month means unpaid now.
            is_paid=p.paid_month == this_month,
        )
        for p in payments_result.scalars().all()
    ]

    today = datetime.now(user_tz()).date()
    result = compute_cash_flow(incomes, payments, today)

    def _out(items) -> list[UpcomingPaymentOut]:
        return [
            UpcomingPaymentOut(
                id=u.id,
                name=u.name,
                amount=u.amount,
                deadline=u.deadline,
                days_left=u.days_left,
                is_debt_payment=u.is_debt_payment,
                is_paid=u.is_paid,
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


# Deposits that are the user's own money moving, never income.
_NOT_INCOME = ("transfer", "debt_payment")


@router.get("/cashflow/position", response_model=CashPositionResponse)
async def cash_position(
    current_user: CurrentUser,
    db: DbSession,
    until: date | None = Query(default=None),
    pay_due_on_payday: bool = Query(default=True),
) -> CashPositionResponse:
    """Fortnight cash position: balance → what's due before the next
    payday → what later paydays can't cover → free. Read-only, computed on
    the fly from accounts, income sources, planned payments and debts.

    ``pay_due_on_payday`` (default on — the user's rule) pays what is due on
    a payday with that payday's money; off = conservative, pay it before.
    """
    tz = user_tz()
    today = datetime.now(tz).date()
    horizon_end = until or default_horizon(today)
    if horizon_end < today:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="past_until")

    snap = await net_worth(db, current_user.id)
    sources = (
        (await db.execute(select(IncomeSource).where(IncomeSource.user_id == current_user.id)))
        .scalars()
        .all()
    )
    payments = (
        (
            await db.execute(
                select(PlannedPayment).where(PlannedPayment.user_id == current_user.id)
            )
        )
        .scalars()
        .all()
    )
    debts = (
        (await db.execute(select(Debt).where(Debt.user_id == current_user.id))).scalars().all()
    )

    # Enough history to spot late deposits and card payments made against a
    # statement that is due up to a month ahead.
    since = datetime.now(tz) - timedelta(days=STATEMENT_WINDOW_DAYS + 10)
    rows = (
        await db.execute(
            select(
                Transaction.occurred_at,
                Transaction.amount,
                Transaction.category,
                Transaction.debt_id,
                Transaction.source,
            ).where(
                Transaction.user_id == current_user.id,
                Transaction.transaction_type == TransactionType.credit,
                Transaction.occurred_at >= since,
            )
        )
    ).all()
    credits = [
        Credit(r.occurred_at.astimezone(tz).date(), r.amount)
        for r in rows
        # Card receipts (source "card") and own transfers aren't income.
        if r.source != "card" and (r.category is None or r.category not in _NOT_INCOME)
    ]
    debt_payments = [
        DebtPayment(r.debt_id, r.occurred_at.astimezone(tz).date(), r.amount)
        for r in rows
        if r.debt_id is not None and r.category == "debt_payment"
    ]

    inputs = build_inputs(
        today=today,
        horizon_end=horizon_end,
        balance=snap.total_assets,
        income_sources=sources,
        credits=credits,
        planned_payments=payments,
        debts=debts,
        debt_payments=debt_payments,
        pay_due_on_payday=pay_due_on_payday,
    )
    pos = compute_position(inputs)
    notes = list(NOTES)
    if not snap.accounts:
        notes.insert(0, "No hay cuentas cargadas en Patrimonio: el saldo es 0.")

    return CashPositionResponse(
        status=pos.status.value,
        today=today,
        horizon_end=horizon_end,
        pay_due_on_payday=pay_due_on_payday,
        balance=pos.balance,
        held_for_others=pos.held_for_others,
        own=pos.own,
        due_before_next_income=pos.due_before_next_income,
        essentials_until_next_income=pos.essentials_until_next_income,
        reserve_for_later=pos.reserve_for_later,
        free=pos.free,
        spendable_now=pos.spendable_now,
        windows=[
            PositionWindowOut(
                start=w.start,
                end=w.end,
                income=w.income,
                income_names=w.income_names,
                obligations=[
                    PositionLineOut(name=o.name, amount=o.amount, estimated=o.estimated)
                    for o in w.obligations
                ],
                essentials=w.essentials,
                balance_after=w.balance_after,
            )
            for w in pos.windows
        ],
        deficit=(
            PositionDeficitOut(
                window_start=pos.deficit.window_start,
                amount=pos.deficit.amount,
                obligations=pos.deficit.obligations,
            )
            if pos.deficit
            else None
        ),
        missing=pos.missing,
        estimated=pos.estimated,
        late_incomes=pos.late_incomes,
        overdue=pos.overdue,
        no_plan=pos.no_plan,
        notes=notes,
    )


async def _get_own(model, obj_id: uuid.UUID, user_id: uuid.UUID, db: DbSession):
    result = await db.execute(
        select(model).where(model.id == obj_id, model.user_id == user_id)
    )
    obj = result.scalar_one_or_none()
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
    return obj
