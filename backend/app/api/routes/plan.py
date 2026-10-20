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
from app.models.account import AccountKind
from app.models.debt import Debt
from app.models.fund_hold import FundHold
from app.models.income_source import IncomeSource
from app.models.obligation_payment import ObligationPayment
from app.models.planned_payment import PlannedPayment
from app.models.transaction import Transaction, TransactionType
from app.schemas.plan import (
    CashFlowResponse,
    CashPositionResponse,
    FundHoldIn,
    FundHoldOut,
    FundHoldUpdate,
    IncomeSourceCreate,
    IncomeSourceOut,
    IncomeSourceUpdate,
    ObligationPaymentIn,
    ObligationPaymentOut,
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
    STATEMENT_WINDOW_DAYS,
    Credit,
    DebtPayment,
    PaymentRecord,
    build_inputs,
    default_horizon,
)
from app.services.net_worth import keep_cash_reconciled, net_worth

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
            due_day=_monthly_due_day(p, this_month),
            grace_days=p.grace_days,
            is_debt_payment=p.is_debt_payment,
            id=p.id,
            # Check-off is per local month; an old paid_month means unpaid now.
            is_paid=p.paid_month == this_month,
        )
        for p in payments_result.scalars().all()
        # A one-off belongs to this month's plan only in (or past) its month.
        if p.due_date is None or f"{p.due_date:%Y-%m}" <= this_month
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
    fund_holds = (
        (await db.execute(select(FundHold).where(FundHold.user_id == current_user.id)))
        .scalars()
        .all()
    )
    records = [
        PaymentRecord(r.due_date, r.amount, r.planned_payment_id, r.debt_id)
        for r in (
            await db.execute(
                select(ObligationPayment).where(
                    ObligationPayment.user_id == current_user.id,
                    ObligationPayment.due_date >= today - timedelta(days=STATEMENT_WINDOW_DAYS),
                )
            )
        )
        .scalars()
        .all()
    ]
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
        fund_holds=fund_holds,
        records=records,
    )
    pos = compute_position(inputs)
    notes: list[str] = []
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
                    PositionLineOut(
                        name=o.name,
                        amount=o.amount,
                        estimated=o.estimated,
                        due=o.due,
                        total=o.total,
                        ref=o.ref,
                    )
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


def _monthly_due_day(p: PlannedPayment, this_month: str) -> int | None:
    if p.due_date is None:
        return p.due_day
    # One-off: its day in its own month; overdue ones show without a date.
    return p.due_date.day if f"{p.due_date:%Y-%m}" == this_month else None


# --- Money held for others ---


@router.get("/fund-holds", response_model=list[FundHoldOut])
async def list_fund_holds(current_user: CurrentUser, db: DbSession) -> list[FundHoldOut]:
    rows = await db.execute(
        select(FundHold).where(FundHold.user_id == current_user.id).order_by(FundHold.created_at)
    )
    return [FundHoldOut.model_validate(h) for h in rows.scalars().all()]


@router.post("/fund-holds", response_model=FundHoldOut, status_code=status.HTTP_201_CREATED)
async def create_fund_hold(
    payload: FundHoldIn, current_user: CurrentUser, db: DbSession
) -> FundHoldOut:
    hold = FundHold(user_id=current_user.id, **payload.model_dump())
    db.add(hold)
    await db.commit()
    await db.refresh(hold)
    return FundHoldOut.model_validate(hold)


@router.patch("/fund-holds/{hold_id}", response_model=FundHoldOut)
async def update_fund_hold(
    hold_id: uuid.UUID, payload: FundHoldUpdate, current_user: CurrentUser, db: DbSession
) -> FundHoldOut:
    hold = await _get_own(FundHold, hold_id, current_user.id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(hold, field, value)
    await db.commit()
    await db.refresh(hold)
    return FundHoldOut.model_validate(hold)


@router.delete("/fund-holds/{hold_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fund_hold(hold_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> None:
    """When that money was handed over or used for what it was for."""
    hold = await _get_own(FundHold, hold_id, current_user.id, db)
    await db.delete(hold)
    await db.commit()


# --- Payments toward a due date ---


@router.get("/obligation-payments", response_model=list[ObligationPaymentOut])
async def list_obligation_payments(
    current_user: CurrentUser,
    db: DbSession,
    since: date | None = Query(default=None),
) -> list[ObligationPaymentOut]:
    query = select(ObligationPayment).where(ObligationPayment.user_id == current_user.id)
    if since is not None:
        query = query.where(ObligationPayment.due_date >= since)
    rows = await db.execute(query.order_by(ObligationPayment.due_date))
    return [ObligationPaymentOut.model_validate(r) for r in rows.scalars().all()]


@router.post(
    "/obligation-payments",
    response_model=ObligationPaymentOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_obligation_payment(
    payload: ObligationPaymentIn, current_user: CurrentUser, db: DbSession
) -> ObligationPaymentOut:
    """Record money put toward one due date (all of it, part, or ahead).

    ``from_cash`` also logs the cash expense: the cash position subtracts
    what's paid from what's owed, so the balance has to drop by the same
    amount or the payment would show up as free money.
    """
    if (payload.planned_payment_id is None) == (payload.debt_id is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="one_parent_required"
        )
    if payload.planned_payment_id is not None:
        parent = await _get_own(PlannedPayment, payload.planned_payment_id, current_user.id, db)
        merchant, category = parent.name, None
    else:
        parent = await _get_own(Debt, payload.debt_id, current_user.id, db)
        # Paying a card isn't spending: its purchases already were.
        merchant, category = f"Pago {parent.bank_name}", "debt_payment"

    tz = user_tz()
    today = datetime.now(tz).date()
    paid_on = payload.paid_on or today
    if paid_on > today:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="future_paid_on")

    tx_id = None
    if payload.from_cash:
        occurred_at = (
            datetime.now(tz)
            if paid_on == today
            else datetime.combine(paid_on, datetime.min.time(), tz).replace(hour=12)
        )
        tx = Transaction(
            user_id=current_user.id,
            provider_connection_id=None,
            amount=payload.amount,
            merchant=merchant,
            category=category,
            transaction_type=TransactionType.debit,
            currency="COP",
            occurred_at=occurred_at,
            source=AccountKind.cash.value,
        )
        db.add(tx)
        await db.flush()
        await keep_cash_reconciled(db, current_user.id, None, (tx.amount, tx.occurred_at))
        tx_id = tx.id

    record = ObligationPayment(
        user_id=current_user.id,
        planned_payment_id=payload.planned_payment_id,
        debt_id=payload.debt_id,
        due_date=payload.due_date,
        amount=payload.amount,
        paid_on=paid_on,
        transaction_id=tx_id,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return ObligationPaymentOut.model_validate(record)


@router.delete("/obligation-payments/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_obligation_payment(
    payment_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> None:
    """Undo a recorded payment; the cash expense it created goes with it."""
    record = await _get_own(ObligationPayment, payment_id, current_user.id, db)
    if record.transaction_id is not None:
        tx = (
            await db.execute(
                select(Transaction).where(
                    Transaction.id == record.transaction_id,
                    Transaction.user_id == current_user.id,
                )
            )
        ).scalar_one_or_none()
        if tx is not None:
            await keep_cash_reconciled(db, current_user.id, (tx.amount, tx.occurred_at), None)
            await db.delete(tx)
    await db.delete(record)
    await db.commit()


async def _get_own(model, obj_id: uuid.UUID, user_id: uuid.UUID, db: DbSession):
    result = await db.execute(
        select(model).where(model.id == obj_id, model.user_id == user_id)
    )
    obj = result.scalar_one_or_none()
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
    return obj
