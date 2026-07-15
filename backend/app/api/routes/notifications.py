"""Push token registry. Mobile registers its Expo push token after login;
the daily alert job fans out to every token a user has. Upsert semantics —
re-registering the same token is a no-op refresh, not a duplicate."""

from __future__ import annotations

from fastapi import APIRouter, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from app.api.deps import CurrentUser, DbSession
from app.models.push_token import PushToken

router = APIRouter(prefix="/notifications", tags=["notifications"])


class PushTokenIn(BaseModel):
    token: str = Field(min_length=1, max_length=255)
    platform: str | None = Field(default=None, max_length=16)


class PushTokenOut(BaseModel):
    registered: bool


@router.post("/token", response_model=PushTokenOut)
async def register_push_token(
    payload: PushTokenIn, current_user: CurrentUser, db: DbSession
) -> PushTokenOut:
    result = await db.execute(
        select(PushToken).where(
            PushToken.user_id == current_user.id, PushToken.token == payload.token
        )
    )
    existing = result.scalar_one_or_none()
    if existing is None:
        db.add(
            PushToken(
                user_id=current_user.id,
                token=payload.token,
                platform=payload.platform,
            )
        )
    else:
        existing.platform = payload.platform or existing.platform
    await db.commit()
    return PushTokenOut(registered=True)


@router.delete("/token", status_code=status.HTTP_204_NO_CONTENT)
async def unregister_push_token(
    payload: PushTokenIn, current_user: CurrentUser, db: DbSession
) -> None:
    await db.execute(
        delete(PushToken).where(
            PushToken.user_id == current_user.id, PushToken.token == payload.token
        )
    )
    await db.commit()
