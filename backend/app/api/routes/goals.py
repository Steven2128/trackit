import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.savings_goal import SavingsGoal
from app.schemas.savings_goal import (
    SavingsGoalCreate,
    SavingsGoalOut,
    SavingsGoalUpdate,
)

router = APIRouter(prefix="/goals", tags=["goals"])


@router.get("", response_model=list[SavingsGoalOut])
async def list_goals(current_user: CurrentUser, db: DbSession) -> list[SavingsGoalOut]:
    result = await db.execute(
        select(SavingsGoal)
        .where(SavingsGoal.user_id == current_user.id)
        .order_by(SavingsGoal.created_at.desc())
    )
    return [SavingsGoalOut.model_validate(g) for g in result.scalars().all()]


@router.post("", response_model=SavingsGoalOut, status_code=status.HTTP_201_CREATED)
async def create_goal(
    payload: SavingsGoalCreate, current_user: CurrentUser, db: DbSession
) -> SavingsGoalOut:
    goal = SavingsGoal(user_id=current_user.id, **payload.model_dump())
    db.add(goal)
    await db.commit()
    await db.refresh(goal)
    return SavingsGoalOut.model_validate(goal)


@router.patch("/{goal_id}", response_model=SavingsGoalOut)
async def update_goal(
    goal_id: uuid.UUID,
    payload: SavingsGoalUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> SavingsGoalOut:
    goal = await _get_own_goal(goal_id, current_user.id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(goal, field, value)
    await db.commit()
    await db.refresh(goal)
    return SavingsGoalOut.model_validate(goal)


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(
    goal_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> None:
    goal = await _get_own_goal(goal_id, current_user.id, db)
    await db.delete(goal)
    await db.commit()


async def _get_own_goal(
    goal_id: uuid.UUID, user_id: uuid.UUID, db: DbSession
) -> SavingsGoal:
    result = await db.execute(
        select(SavingsGoal).where(
            SavingsGoal.id == goal_id, SavingsGoal.user_id == user_id
        )
    )
    goal = result.scalar_one_or_none()
    if goal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="goal_not_found")
    return goal
