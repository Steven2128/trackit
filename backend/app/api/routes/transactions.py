"""Read endpoints for transactions.

Month windowing respects ``settings.user_timezone`` (default America/Bogota)
because the user reasons about months in local time. Transactions are stored
in UTC, so we convert the local-month boundaries to UTC at query time.

Spending totals exclude internal movements (transfers between the user's own
accounts and cash withdrawals) per PARSERS.md — those still appear in the
raw list, just don't inflate ``total_spent`` / ``total_received``.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.sql import ColumnElement

from app.api.deps import CurrentUser, DbSession
from app.core.time_utils import current_month_local, month_filter, not_in_excluded
from app.models.account import AccountKind
from app.models.contact import Contact
from app.models.debt import Debt
from app.models.transaction import OWN_AMOUNT, Transaction, TransactionType
from app.schemas.account import CashExpenseIn
from app.schemas.transaction import (
    CategorySummaryItem,
    ContactBalance,
    ManualMovementIn,
    SharedSummary,
    TransactionListResponse,
    TransactionOut,
    TransactionSummary,
    TransactionUpdate,
)
from app.services.categorizer import RULES
from app.services.contact_balance import CONTACT_SOURCE, balance_effect
from app.services.net_worth import (
    MANUAL_ACCOUNT_SOURCES,
    CashExpense,
    keep_cash_reconciled,
    keep_reconciled,
    outflow,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])

# "reimbursement": money between the user and a contact — paying back their
# part of a shared expense, or lending — is neither income nor spending
# (see Transaction.shared_amount and services/contact_balance.py).
EXCLUDED_FROM_SPENT_CATEGORIES = ("transfer", "cash_withdrawal", "debt_payment", "reimbursement")
EXCLUDED_FROM_RECEIVED_CATEGORIES = ("transfer", "debt_payment", "reimbursement")

# Manual recategorization accepts anything the system itself can emit:
# categorizer rules plus the layers reserved to transfer_matcher/parsers.
ALLOWED_CATEGORIES = {rule.category for rule in RULES} | set(
    EXCLUDED_FROM_SPENT_CATEGORIES + EXCLUDED_FROM_RECEIVED_CATEGORIES
)

# User-defined categories are free-form slugs (mobile slugifies the display
# name). No registry table — a custom category exists while a budget or a
# transaction references it; budgets/status and dashboards group by string.
CUSTOM_CATEGORY_RE = re.compile(r"^[a-z0-9_]{1,64}$")


@router.get("", response_model=TransactionListResponse)
async def list_transactions(
    current_user: CurrentUser,
    db: DbSession,
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    category: str | None = Query(default=None),
    type: TransactionType | None = Query(default=None),
    debt_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> TransactionListResponse:
    filters = [Transaction.user_id == current_user.id]
    filters.extend(month_filter(month))
    if category is not None:
        filters.append(Transaction.category == category)
    if type is not None:
        filters.append(Transaction.transaction_type == type)
    if debt_id is not None:
        filters.append(Transaction.debt_id == debt_id)

    total_result = await db.execute(
        select(func.count()).select_from(Transaction).where(*filters)
    )
    total = total_result.scalar_one()

    rows_result = await db.execute(
        select(Transaction)
        .where(*filters)
        .order_by(Transaction.occurred_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = [TransactionOut.model_validate(t) for t in rows_result.scalars().all()]

    return TransactionListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/shared", response_model=SharedSummary)
async def shared_summary(current_user: CurrentUser, db: DbSession) -> SharedSummary:
    """What others owe for shared expenses: the sum of their parts minus
    what came back as reimbursements. All time — it's a running balance,
    like a tab with the brother."""
    # The three totals cover what isn't assigned to anyone yet.
    unassigned = Transaction.contact_id.is_(None)
    covered = await _sum_shared(
        db,
        [
            Transaction.user_id == current_user.id,
            Transaction.shared_amount.is_not(None),
            unassigned,
        ],
    )
    reimbursed = await _sum_amount(
        db,
        [
            Transaction.user_id == current_user.id,
            Transaction.transaction_type == TransactionType.credit,
            Transaction.category == "reimbursement",
            unassigned,
        ],
    )
    contacts = (
        (await db.execute(select(Contact).where(Contact.user_id == current_user.id)))
        .scalars()
        .all()
    )
    named = (
        (
            await db.execute(
                select(Transaction).where(
                    Transaction.user_id == current_user.id,
                    Transaction.contact_id.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )
    people = contact_balances(contacts, named)
    rows = await db.execute(
        select(Transaction)
        .where(
            Transaction.user_id == current_user.id,
            Transaction.shared_amount.is_not(None)
            | (Transaction.category == "reimbursement")
            | Transaction.contact_id.is_not(None),
        )
        .order_by(Transaction.occurred_at.desc())
        .limit(60)
    )
    return SharedSummary(
        covered_for_others=covered,
        reimbursed=reimbursed,
        pending=max(covered - reimbursed, Decimal("0")),
        people=people,
        items=[TransactionOut.model_validate(t) for t in rows.scalars().all()],
    )


def contact_balances(contacts, rows) -> list[ContactBalance]:
    """One balance per contact (zero ones included, so they can be picked),
    biggest debts first."""
    totals = {c.id: Decimal("0") for c in contacts}
    for row in rows:
        if row.contact_id in totals:
            totals[row.contact_id] += balance_effect(row)
    people = [ContactBalance(contact_id=c.id, name=c.name, balance=totals[c.id]) for c in contacts]
    return sorted(people, key=lambda p: (-abs(p.balance), p.name.lower()))


async def _sum_shared(db, filters: list[ColumnElement]) -> Decimal:
    value = (
        await db.execute(
            select(func.coalesce(func.sum(Transaction.shared_amount), 0)).where(*filters)
        )
    ).scalar_one()
    return Decimal(value) if not isinstance(value, Decimal) else value


@router.post("/cash", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
async def create_cash_expense(
    payload: CashExpenseIn, current_user: CurrentUser, db: DbSession
) -> TransactionOut:
    """A cash expense typed by the user — no email exists for it. Counts as
    spending and lowers the cash account (services/net_worth.py)."""
    if payload.category is not None and not _is_allowed_category(payload.category):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="unknown_category"
        )
    tx = Transaction(
        user_id=current_user.id,
        provider_connection_id=None,
        amount=payload.amount,
        merchant=payload.merchant.strip(),
        category=payload.category,
        transaction_type=TransactionType.debit,
        currency="COP",
        occurred_at=payload.occurred_at or datetime.now(timezone.utc),
        source="cash",
    )
    db.add(tx)
    await keep_cash_reconciled(db, current_user.id, None, (tx.amount, tx.occurred_at))
    await db.commit()
    await db.refresh(tx)
    return TransactionOut.model_validate(tx)


@router.post("/manual", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
async def create_manual_movement(
    payload: ManualMovementIn, current_user: CurrentUser, db: DbSession
) -> TransactionOut:
    """A movement with no email: a payback that came by "llave", money lent,
    or an expense a contact paid (``account="contact"``: only the user's part
    counts as spending and no account moves). Dated before the account's last
    reconciliation, it's absorbed by that adjustment so the balance the user
    already checked stays put."""
    if payload.category is not None and not _is_allowed_category(payload.category):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="unknown_category"
        )
    if payload.contact_id is not None:
        await _own_contact(db, current_user.id, payload.contact_id)
    shared = payload.shared_amount or None
    if payload.account == CONTACT_SOURCE:
        if payload.transaction_type != TransactionType.debit or payload.contact_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="contact_paid_needs_debit",
            )
        # Their part may be 0: they paid something that was all the user's.
        shared = payload.shared_amount or Decimal("0")
    elif shared is not None and payload.transaction_type != TransactionType.debit:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="shared_needs_debit"
        )
    if shared is not None and shared > payload.amount:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="shared_exceeds_amount"
        )
    tx = Transaction(
        user_id=current_user.id,
        provider_connection_id=None,
        amount=payload.amount,
        merchant=payload.merchant.strip(),
        category=payload.category,
        transaction_type=payload.transaction_type,
        currency="COP",
        occurred_at=payload.occurred_at or datetime.now(timezone.utc),
        source=payload.account,
        shared_amount=shared,
        contact_id=payload.contact_id,
        note=(payload.note or "").strip() or None,
    )
    db.add(tx)
    await _reconcile(db, current_user.id, tx.source, None, _outflow(tx))
    await db.commit()
    await db.refresh(tx)
    return TransactionOut.model_validate(tx)


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cash_expense(
    transaction_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> None:
    """Only typed-in movements can be deleted; email rows would just come
    back on the next sync."""
    tx = (
        await db.execute(
            select(Transaction).where(
                Transaction.id == transaction_id, Transaction.user_id == current_user.id
            )
        )
    ).scalar_one_or_none()
    if tx is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="transaction_not_found")
    if not _editable(tx):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="not_a_manual_transaction")
    await _reconcile(db, current_user.id, tx.source, _outflow(tx), None)
    await db.delete(tx)
    await db.commit()


def _is_allowed_category(category: str) -> bool:
    return category in ALLOWED_CATEGORIES or bool(CUSTOM_CATEGORY_RE.match(category))


def _editable(tx: Transaction) -> bool:
    """Cash rows and anything typed in: there's no email to diverge from."""
    return tx.source == "cash" or bool(getattr(tx, "manual", False))


def _outflow(tx: Transaction) -> CashExpense:
    return outflow(tx.transaction_type, tx.amount, tx.occurred_at)


async def _reconcile(
    db: DbSession,
    user_id: uuid.UUID,
    source: str | None,
    before: CashExpense,
    after: CashExpense,
) -> None:
    """Keep the last reconciliation of the account a typed-in row moves."""
    kind = MANUAL_ACCOUNT_SOURCES.get(source or "")
    if kind is AccountKind.cash:
        await keep_cash_reconciled(db, user_id, before, after)
    elif kind is not None:
        await keep_reconciled(db, user_id, kind, before, after)


async def _own_contact(db: DbSession, user_id: uuid.UUID, contact_id: uuid.UUID) -> None:
    found = (
        await db.execute(
            select(Contact.id).where(Contact.id == contact_id, Contact.user_id == user_id)
        )
    ).scalar_one_or_none()
    if found is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="contact_not_found")


async def _own_debt(db: DbSession, user_id: uuid.UUID, debt_id: uuid.UUID) -> Debt | None:
    return (
        await db.execute(select(Debt).where(Debt.id == debt_id, Debt.user_id == user_id))
    ).scalar_one_or_none()


async def _relink_debt(
    db: DbSession, user_id: uuid.UUID, tx: Transaction, debt_id: uuid.UUID | None
) -> None:
    """Point a debit at the hand-entered debt it paid.

    Manual debts have no email to lower their balance, so the link does it;
    moving or clearing the link gives the amount back to the old debt.
    Email-linked cards are refused on both ends: their own payment email
    already lowers the balance and counts toward the due date, so a bank
    debit linked to them too would count twice.
    """
    if debt_id == tx.debt_id:
        return
    if tx.transaction_type != TransactionType.debit:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="debt_needs_debit"
        )
    old = await _own_debt(db, user_id, tx.debt_id) if tx.debt_id is not None else None
    if tx.source == "card" or (old is not None and old.email_sender):
        # A card purchase read from the card's emails: its debt is the card.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="debt_not_editable")
    new = None
    if debt_id is not None:
        new = await _own_debt(db, user_id, debt_id)
        if new is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="debt_not_found")
        if new.email_sender:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="debt_has_email"
            )
    if old is not None:
        old.total_amount = old.total_amount + tx.amount
    if new is not None:
        new.total_amount = max(new.total_amount - tx.amount, Decimal(0))
        tx.category = "debt_payment"
    tx.debt_id = debt_id


@router.patch("/{transaction_id}", response_model=TransactionOut)
async def update_transaction(
    transaction_id: uuid.UUID,
    payload: TransactionUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> TransactionOut:
    """Manual edit (category, merchant name, note, shared part, contact, the manual debt a
    debit paid; amount and date for cash and typed-in movements)
    — feeds budget bars, summaries, dashboard and the cash balance. Partial:
    only fields present in the body change."""
    provided = payload.model_fields_set
    if not provided:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="empty_update"
        )

    if "category" in provided and payload.category is not None:
        if not _is_allowed_category(payload.category):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="unknown_category",
            )

    merchant: str | None = None
    if "merchant" in provided and payload.merchant is not None:
        merchant = payload.merchant.strip()
        if not merchant or len(merchant) > 255:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="invalid_merchant",
            )

    note: str | None = None
    if "note" in provided and payload.note is not None:
        note = payload.note.strip() or None
        if note is not None and len(note) > 500:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="invalid_note",
            )

    result = await db.execute(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == current_user.id,
        )
    )
    tx = result.scalar_one_or_none()
    if tx is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="transaction_not_found"
        )

    if "category" in provided:
        tx.category = payload.category
    if "merchant" in provided:
        tx.merchant = merchant
    if "note" in provided:
        tx.note = note
    before = _outflow(tx)
    if "amount" in provided:
        if payload.amount is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid_amount"
            )
        # Bank rows mirror their notification email; editing the amount would
        # just diverge from the bank (and from the statement reconciler).
        if not _editable(tx):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="amount_not_editable"
            )
        tx.amount = payload.amount
    if "occurred_at" in provided:
        if payload.occurred_at is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid_date"
            )
        # Same reason: a bank row's date is the one in its email.
        if not _editable(tx):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="date_not_editable"
            )
        tx.occurred_at = payload.occurred_at
    if "shared_amount" in provided:
        shared = payload.shared_amount or None  # 0 clears it
        if shared is not None and tx.transaction_type != TransactionType.debit:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="shared_needs_debit"
            )
        tx.shared_amount = shared
    if "debt_id" in provided:
        await _relink_debt(db, current_user.id, tx, payload.debt_id)
    if "contact_id" in provided:
        if payload.contact_id is not None:
            await _own_contact(db, current_user.id, payload.contact_id)
        elif tx.source == CONTACT_SOURCE:
            # Without them it'd be an expense nobody paid.
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="contact_required"
            )
        tx.contact_id = payload.contact_id
    if tx.shared_amount is not None and tx.shared_amount > tx.amount:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="shared_exceeds_amount"
        )
    if provided & {"amount", "occurred_at"}:
        await _reconcile(db, current_user.id, tx.source, before, _outflow(tx))
    await db.commit()
    await db.refresh(tx)
    return TransactionOut.model_validate(tx)


@router.get("/summary", response_model=TransactionSummary)
async def transactions_summary(
    current_user: CurrentUser,
    db: DbSession,
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
) -> TransactionSummary:
    resolved_month = month or current_month_local()
    month_clauses = month_filter(resolved_month)
    base_filter = [Transaction.user_id == current_user.id, *month_clauses]

    total_spent = await _sum_amount(
        db,
        [
            *base_filter,
            Transaction.transaction_type == TransactionType.debit,
            not_in_excluded(Transaction.category, EXCLUDED_FROM_SPENT_CATEGORIES),
        ],
    )
    total_received = await _sum_amount(
        db,
        [
            *base_filter,
            Transaction.transaction_type == TransactionType.credit,
            not_in_excluded(Transaction.category, EXCLUDED_FROM_RECEIVED_CATEGORIES),
        ],
    )

    by_category_rows = await db.execute(
        select(
            Transaction.category,
            func.coalesce(func.sum(OWN_AMOUNT), 0).label("total"),
            func.count().label("count"),
        )
        .where(
            *base_filter,
            Transaction.transaction_type == TransactionType.debit,
            not_in_excluded(Transaction.category, EXCLUDED_FROM_SPENT_CATEGORIES),
        )
        .group_by(Transaction.category)
        .order_by(func.sum(OWN_AMOUNT).desc())
    )
    by_category = [
        CategorySummaryItem(category=row.category, total=row.total, count=row.count)
        for row in by_category_rows.all()
    ]

    count_result = await db.execute(
        select(func.count()).select_from(Transaction).where(*base_filter)
    )
    transaction_count = count_result.scalar_one()

    return TransactionSummary(
        month=resolved_month,
        total_spent=total_spent,
        total_received=total_received,
        by_category=by_category,
        transaction_count=transaction_count,
    )


async def _sum_amount(db, filters: list[ColumnElement]) -> Decimal:
    result = await db.execute(
        select(func.coalesce(func.sum(OWN_AMOUNT), 0)).where(*filters)
    )
    value = result.scalar_one()
    return Decimal(value) if not isinstance(value, Decimal) else value
