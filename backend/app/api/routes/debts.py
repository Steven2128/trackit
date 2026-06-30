import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.debt import Debt
from app.schemas.debt import DebtCreate, DebtOut, DebtUpdate

router = APIRouter(prefix="/debts", tags=["debts"])


@router.get("", response_model=list[DebtOut])
async def list_debts(current_user: CurrentUser, db: DbSession) -> list[DebtOut]:
    result = await db.execute(
        select(Debt)
        .where(Debt.user_id == current_user.id)
        .order_by(Debt.created_at.desc())
    )
    return [DebtOut.model_validate(d) for d in result.scalars().all()]


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
