"""Accounts and net worth (patrimonio).

Balances are computed in services/net_worth.py from an opening balance the
user types plus the movements read from email since then. Reconciling stores
the difference with the real balance as a visible adjustment.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, select

from app.api.deps import CurrentUser, DbSession
from app.models.account import Account, AccountAdjustment, AccountKind
from app.schemas.account import (
    AccountOut,
    AccountUpsert,
    NetWorthOut,
    ReconcileIn,
    ReconcileOut,
)
from app.services.net_worth import account_balance, net_worth

router = APIRouter(prefix="/accounts", tags=["accounts"])

DEFAULT_NAMES = {
    AccountKind.davivienda: "Davivienda",
    AccountKind.nequi: "Nequi",
    AccountKind.cash: "Efectivo",
}


@router.get("", response_model=NetWorthOut)
async def get_net_worth(current_user: CurrentUser, db: DbSession) -> NetWorthOut:
    snap = await net_worth(db, current_user.id)
    return NetWorthOut(
        accounts=[
            AccountOut(
                id=s.account.id,
                kind=s.account.kind,
                name=s.account.name,
                opening_balance=s.account.opening_balance,
                opening_at=s.account.opening_at,
                balance=s.balance,
                last_reconciled_at=s.last_reconciled_at,
                unexplained_this_month=s.unexplained_this_month,
            )
            for s in snap.accounts
        ],
        total_assets=snap.total_assets,
        total_debt=snap.total_debt,
        net_worth=snap.net_worth,
        unexplained_this_month=snap.unexplained_this_month,
    )


@router.put("/{kind}", status_code=status.HTTP_204_NO_CONTENT)
async def upsert_account(
    kind: AccountKind, payload: AccountUpsert, current_user: CurrentUser, db: DbSession
) -> None:
    """Create the account or restart it from a new opening balance. Restarting
    drops past adjustments — they were relative to the old starting point."""
    account = await _get_account(db, current_user.id, kind)
    now = datetime.now(timezone.utc)
    if account is None:
        db.add(
            Account(
                user_id=current_user.id,
                kind=kind,
                name=payload.name or DEFAULT_NAMES[kind],
                opening_balance=payload.opening_balance,
                opening_at=now,
            )
        )
    else:
        account.opening_balance = payload.opening_balance
        account.opening_at = now
        if payload.name:
            account.name = payload.name
        await db.execute(delete(AccountAdjustment).where(AccountAdjustment.account_id == account.id))
    await db.commit()


@router.post("/{kind}/reconcile", response_model=ReconcileOut)
async def reconcile_account(
    kind: AccountKind, payload: ReconcileIn, current_user: CurrentUser, db: DbSession
) -> ReconcileOut:
    account = await _get_account(db, current_user.id, kind)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="account_not_found")
    computed = await account_balance(db, account)
    difference = payload.balance - computed
    # Recorded even when zero: it timestamps "last checked and it matched".
    db.add(
        AccountAdjustment(
            account_id=account.id, amount=difference, reported_balance=payload.balance
        )
    )
    await db.commit()
    return ReconcileOut(
        computed_balance=computed, reported_balance=payload.balance, difference=difference
    )


@router.delete("/{kind}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(kind: AccountKind, current_user: CurrentUser, db: DbSession) -> None:
    account = await _get_account(db, current_user.id, kind)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="account_not_found")
    await db.delete(account)
    await db.commit()


async def _get_account(db, user_id, kind: AccountKind) -> Account | None:
    return (
        await db.execute(select(Account).where(Account.user_id == user_id, Account.kind == kind))
    ).scalar_one_or_none()
