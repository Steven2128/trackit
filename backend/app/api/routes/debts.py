import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.time_utils import user_tz
from app.models.card_statement import SavedStatement
from app.models.debt import Debt
from app.models.transaction import Transaction, TransactionType
from app.parsers.cards import CARD_FORMATS
from app.schemas.debt import (
    CardFormatOut,
    DebtCreate,
    DebtOut,
    DebtPayoffOut,
    DebtUpdate,
    StrategyComparisonOut,
    StrategyResultOut,
)
from app.services.cards import current_card_payment
from app.services.debt_strategy import DebtLike, StrategyResult, compare_strategies

router = APIRouter(prefix="/debts", tags=["debts"])


@router.get("", response_model=list[DebtOut])
async def list_debts(current_user: CurrentUser, db: DbSession) -> list[DebtOut]:
    result = await db.execute(
        select(Debt)
        .where(Debt.user_id == current_user.id)
        .order_by(Debt.created_at.desc())
    )
    debts = result.scalars().all()
    current = await _current_card_payments(db, current_user.id, debts)
    out = []
    for d in debts:
        item = DebtOut.model_validate(d)
        payment = current.get(d.id)
        if payment is not None:
            item = item.model_copy(
                update={
                    "current_minimum_payment": payment.amount,
                    "current_due_date": payment.due_date,
                    "current_is_estimate": payment.accruing,
                }
            )
        out.append(item)
    return out


async def _current_card_payments(db, user_id: uuid.UUID, debts) -> dict:
    """Current minimum and due date of the email-linked cards with a
    statement; due dates come from the saved statements when there are."""
    cards = [d for d in debts if d.email_format is not None and d.statement_at is not None]
    if not cards:
        return {}
    ids = [d.id for d in cards]
    latest: dict[uuid.UUID, SavedStatement] = {}
    for st in (
        await db.execute(
            select(SavedStatement)
            .where(SavedStatement.debt_id.in_(ids))
            .order_by(SavedStatement.period_end.desc())
        )
    ).scalars():
        latest.setdefault(st.debt_id, st)
    movements = (
        await db.execute(
            select(
                Transaction.debt_id,
                Transaction.occurred_at,
                Transaction.amount,
                Transaction.transaction_type,
            ).where(
                Transaction.user_id == user_id,
                Transaction.debt_id.in_(ids),
                Transaction.source == "card",
                Transaction.occurred_at >= min(d.statement_at for d in cards),
            )
        )
    ).all()
    tz = user_tz()
    out = {}
    for d in cards:
        st = latest.get(d.id)
        since = [m for m in movements if m.debt_id == d.id and m.occurred_at >= d.statement_at]
        # A statement newer than the saved PDF (email only) wins.
        use_saved = st is not None and st.due_date is not None and (
            d.payment_due_date is None or st.due_date >= d.payment_due_date
        )
        payment = current_card_payment(
            statement_minimum=st.minimum_payment if use_saved else d.minimum_payment,
            statement_due=st.due_date if use_saved else d.payment_due_date,
            cutoff=st.period_end if use_saved else None,
            paid_since_cutoff=sum(
                (m.amount for m in since if m.transaction_type is TransactionType.credit),
                Decimal("0"),
            ),
            purchases_since_cutoff=[
                (m.occurred_at.astimezone(tz).date(), m.amount)
                for m in since
                if m.transaction_type is TransactionType.debit
            ],
            next_installments=d.next_installments,
            balance=d.total_amount,
        )
        if payment is not None:
            out[d.id] = payment
    return out


@router.get("/card-formats", response_model=list[CardFormatOut])
async def list_card_formats(current_user: CurrentUser) -> list[CardFormatOut]:
    """Credit-card email templates the app can link a debt's sender to."""
    return [
        CardFormatOut(key=p.key, label=p.label, default_sender=p.default_sender)
        for p in CARD_FORMATS.values()
    ]


@router.get("/strategy", response_model=StrategyComparisonOut)
async def debt_strategy(
    current_user: CurrentUser,
    db: DbSession,
    extra_monthly: Decimal = Query(
        default=Decimal("0"),
        ge=0,
        description="Monthly amount available on top of all minimum payments.",
    ),
) -> StrategyComparisonOut:
    """Compare avalanche vs snowball payoff plans over the user's debts.

    Computed on the fly like /dashboard and /subscriptions — no persisted state.
    """
    result = await db.execute(select(Debt).where(Debt.user_id == current_user.id))
    debts = [
        DebtLike(
            name=d.bank_name,
            balance=d.total_amount,
            annual_rate=d.interest_rate,
            minimum_payment=d.minimum_payment,
        )
        for d in result.scalars().all()
    ]
    if not debts:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no_debts")

    comparison = compare_strategies(debts, extra_monthly)
    return StrategyComparisonOut(
        avalanche=_to_result_out(comparison.avalanche),
        snowball=_to_result_out(comparison.snowball),
        interest_saved_by_avalanche=comparison.interest_saved_by_avalanche,
        months_saved_by_avalanche=comparison.months_saved_by_avalanche,
        recommended=comparison.recommended,
    )


def _to_result_out(result: StrategyResult) -> StrategyResultOut:
    return StrategyResultOut(
        strategy=result.strategy,
        months_to_free=result.months_to_free,
        total_interest=result.total_interest,
        total_paid=result.total_paid,
        payoff_order=result.payoff_order,
        per_debt=[
            DebtPayoffOut(
                name=p.name,
                payoff_month=p.payoff_month,
                interest_paid=p.interest_paid,
            )
            for p in result.per_debt
        ],
        converges=result.converges,
    )


@router.post("", response_model=DebtOut, status_code=status.HTTP_201_CREATED)
async def create_debt(
    payload: DebtCreate, current_user: CurrentUser, db: DbSession
) -> DebtOut:
    data = payload.model_dump()
    _validate_email_link(data.get("email_sender"), data.get("email_format"))
    debt = Debt(user_id=current_user.id, **data)
    if debt.email_sender:
        debt.email_linked_at = datetime.now(timezone.utc)
    db.add(debt)
    await db.commit()
    await db.refresh(debt)
    return DebtOut.model_validate(debt)


@router.patch("/{debt_id}", response_model=DebtOut)
async def update_debt(
    debt_id: uuid.UUID,
    payload: DebtUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> DebtOut:
    debt = await _get_own_debt(debt_id, current_user.id, db)
    changes = payload.model_dump(exclude_unset=True)
    sender = changes.get("email_sender", debt.email_sender)
    email_format = changes.get("email_format", debt.email_format)
    _validate_email_link(sender, email_format)
    relinked = sender != debt.email_sender or email_format != debt.email_format
    for field, value in changes.items():
        setattr(debt, field, value)
    if relinked:
        # The balance the user sees now is the new starting point; only card
        # movements after this instant move it (see apply_card_event_to_balance).
        debt.email_linked_at = datetime.now(timezone.utc) if sender else None
        if not sender:
            debt.email_format = None
            debt.card_last_digits = None
    await db.commit()
    await db.refresh(debt)
    return DebtOut.model_validate(debt)


@router.delete("/{debt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_debt(
    debt_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> None:
    debt = await _get_own_debt(debt_id, current_user.id, db)
    await db.delete(debt)
    await db.commit()


async def _get_own_debt(debt_id: uuid.UUID, user_id: uuid.UUID, db: DbSession) -> Debt:
    result = await db.execute(
        select(Debt).where(Debt.id == debt_id, Debt.user_id == user_id)
    )
    debt = result.scalar_one_or_none()
    if debt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="debt_not_found")
    return debt


def _validate_email_link(sender: str | None, email_format: str | None) -> None:
    if sender and email_format not in CARD_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="unknown_card_format"
        )
