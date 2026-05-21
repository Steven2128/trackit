import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser
from app.schemas.debt import DebtCreate, DebtOut, DebtUpdate

router = APIRouter(prefix="/debts", tags=["debts"])


@router.get("", response_model=list[DebtOut])
async def list_debts(current_user: CurrentUser) -> list[DebtOut]:
    return []


@router.post("", response_model=DebtOut, status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def create_debt(payload: DebtCreate, current_user: CurrentUser) -> DebtOut:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="POST /debts is not implemented yet",
    )


@router.patch("/{debt_id}", response_model=DebtOut, status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def update_debt(
    debt_id: uuid.UUID,
    payload: DebtUpdate,
    current_user: CurrentUser,
) -> DebtOut:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"PATCH /debts/{debt_id} is not implemented yet",
    )
