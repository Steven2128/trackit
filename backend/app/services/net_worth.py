"""Account balances and net worth.

Bank emails carry movements, never balances, so each balance is computed:

    opening_balance (typed by the user at opening_at)
    + Σ signed movements of that account after opening_at
    + Σ reconciliation adjustments

Computing instead of incrementing a stored balance means a re-synced or
re-categorized email can never be applied twice. Which account a movement
touches comes from ``Transaction.source`` (the parser that read it):

- davivienda / nequi: every credit adds, every debit subtracts — transfers
  and card payments included, since that money did leave/enter the account.
  A Davivienda → Nequi transfer subtracts on one side and adds on the other,
  so net worth doesn't move.
- cash: ATM withdrawals from a bank ("cash_withdrawal") add; cash expenses the
  user types in (source "cash") subtract.
- card (credit-card emails) never touches an account: purchases raise the
  debt instead, and the payment shows up as the funding bank debit.

Net worth = Σ account balances − Σ debt balances.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import current_month_local, month_bounds
from app.models.account import Account, AccountAdjustment, AccountKind
from app.models.debt import Debt
from app.models.transaction import Transaction, TransactionType

# Transaction.source values whose movements belong to each bank account.
BANK_SOURCES: dict[AccountKind, str] = {
    AccountKind.davivienda: "davivienda",
    AccountKind.nequi: "nequi",
}
CASH_SOURCE = "cash"
_WITHDRAWAL_SOURCES = ("davivienda", "nequi", "itau_co")


@dataclass(frozen=True)
class Movement:
    source: str | None
    transaction_type: TransactionType
    category: str | None
    amount: Decimal
    occurred_at: datetime


def account_delta(kind: AccountKind, m: Movement) -> Decimal:
    """Signed effect of one movement on an account of ``kind`` (0 if none)."""
    signed = m.amount if m.transaction_type == TransactionType.credit else -m.amount
    if kind in BANK_SOURCES:
        return signed if m.source == BANK_SOURCES[kind] else Decimal("0")
    # Cash: withdrawals land here; typed-in cash movements move it directly.
    if m.source == CASH_SOURCE:
        return signed
    if (
        m.source in _WITHDRAWAL_SOURCES
        and m.category == "cash_withdrawal"
        and m.transaction_type == TransactionType.debit
    ):
        return m.amount
    return Decimal("0")


def computed_balance(
    kind: AccountKind,
    opening_balance: Decimal,
    opening_at: datetime,
    movements: Iterable[Movement],
    adjustments_total: Decimal = Decimal("0"),
) -> Decimal:
    total = opening_balance + adjustments_total
    for m in movements:
        if m.occurred_at >= opening_at:
            total += account_delta(kind, m)
    return total


@dataclass
class AccountSnapshot:
    account: Account
    balance: Decimal
    last_reconciled_at: datetime | None
    unexplained_this_month: Decimal


@dataclass
class NetWorthSnapshot:
    accounts: list[AccountSnapshot]
    total_assets: Decimal
    total_debt: Decimal
    net_worth: Decimal
    unexplained_this_month: Decimal


async def account_balance(db: AsyncSession, account: Account) -> Decimal:
    """Current computed balance of one account (used by reconcile)."""
    movements = await _movements_since(db, account.user_id, account.opening_at)
    adjustments = (
        await db.execute(
            select(func.coalesce(func.sum(AccountAdjustment.amount), 0)).where(
                AccountAdjustment.account_id == account.id
            )
        )
    ).scalar_one()
    return computed_balance(
        account.kind, account.opening_balance, account.opening_at, movements, Decimal(adjustments)
    )


async def net_worth(db: AsyncSession, user_id: uuid.UUID) -> NetWorthSnapshot:
    accounts = (
        (await db.execute(select(Account).where(Account.user_id == user_id).order_by(Account.created_at)))
        .scalars()
        .all()
    )
    total_debt = Decimal(
        (
            await db.execute(
                select(func.coalesce(func.sum(Debt.total_amount), 0)).where(Debt.user_id == user_id)
            )
        ).scalar_one()
    )
    if not accounts:
        return NetWorthSnapshot([], Decimal("0"), total_debt, -total_debt, Decimal("0"))

    movements = await _movements_since(db, user_id, min(a.opening_at for a in accounts))

    month_start, month_end = month_bounds(current_month_local())
    adj_rows = (
        await db.execute(
            select(AccountAdjustment).where(
                AccountAdjustment.account_id.in_([a.id for a in accounts])
            )
        )
    ).scalars().all()
    adj_total: dict[uuid.UUID, Decimal] = defaultdict(lambda: Decimal("0"))
    adj_month: dict[uuid.UUID, Decimal] = defaultdict(lambda: Decimal("0"))
    last_rec: dict[uuid.UUID, datetime] = {}
    for adj in adj_rows:
        adj_total[adj.account_id] += adj.amount
        if month_start <= adj.created_at < month_end:
            adj_month[adj.account_id] += adj.amount
        if adj.account_id not in last_rec or adj.created_at > last_rec[adj.account_id]:
            last_rec[adj.account_id] = adj.created_at

    snapshots = [
        AccountSnapshot(
            account=a,
            balance=computed_balance(
                a.kind, a.opening_balance, a.opening_at, movements, adj_total[a.id]
            ),
            last_reconciled_at=last_rec.get(a.id),
            unexplained_this_month=adj_month[a.id],
        )
        for a in accounts
    ]
    assets = sum((s.balance for s in snapshots), Decimal("0"))
    return NetWorthSnapshot(
        accounts=snapshots,
        total_assets=assets,
        total_debt=total_debt,
        net_worth=assets - total_debt,
        unexplained_this_month=sum((s.unexplained_this_month for s in snapshots), Decimal("0")),
    )


async def _movements_since(db: AsyncSession, user_id: uuid.UUID, since: datetime) -> list[Movement]:
    rows = await db.execute(
        select(
            Transaction.source,
            Transaction.transaction_type,
            Transaction.category,
            Transaction.amount,
            Transaction.occurred_at,
        ).where(
            Transaction.user_id == user_id,
            Transaction.occurred_at >= since,
            Transaction.source.is_not(None),
        )
    )
    return [Movement(*r) for r in rows.all()]
