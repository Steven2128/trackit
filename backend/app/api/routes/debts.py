import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.debt import Debt
from app.schemas.debt import (
    DebtCreate,
    DebtOut,
    DebtPayoffOut,
    DebtUpdate,
    StrategyComparisonOut,
    StrategyResultOut,
)
from app.services.debt_strategy import DebtLike, StrategyResult, compare_strategies

router = APIRouter(prefix="/debts", tags=["debts"])


@router.get("", response_model=list[DebtOut])
async def list_debts(current_user: CurrentUser, db: DbSession) -> list[DebtOut]:
    result = await db.execute(
        select(Debt)
        .where(Debt.user_id == current_user.id)
        .order_by(Debt.created_at.desc())
    )
    return [DebtOut.model_validate(d) for d in result.scalars().all()]


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
    debt = Debt(user_id=current_user.id, **payload.model_dump())
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
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(debt, field, value)
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
