from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.schemas.transaction import TransactionOut, TransactionSummary

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=list[TransactionOut])
async def list_transactions(current_user: CurrentUser) -> list[TransactionOut]:
    return []


@router.get("/summary", response_model=TransactionSummary)
async def transactions_summary(current_user: CurrentUser) -> TransactionSummary:
    return TransactionSummary()
