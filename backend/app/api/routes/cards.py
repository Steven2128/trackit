"""Credit cards: balance, the statement to pay, the one being built, the
purchases in installments and every saved statement with its movements.

A card is a debt linked to a card email format. Computed on the fly from
the debt, its saved statements (card_statements) and its movements.
"""

import uuid
from collections import defaultdict
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.time_utils import user_tz
from app.models.card_statement import SavedStatement, SavedStatementLine
from app.models.debt import Debt
from app.models.transaction import Transaction, TransactionType
from app.schemas.card import (
    CardOut,
    CardPurchaseOut,
    InstallmentPlanOut,
    StatementDetailOut,
    StatementLineOut,
    StatementSummaryOut,
)
from app.services.cards import add_month, installment_plans, statement_totals

router = APIRouter(prefix="/cards", tags=["cards"])

ZERO = Decimal("0")


def _summary(st: SavedStatement, lines: list[SavedStatementLine]) -> StatementSummaryOut:
    purchases, payments = statement_totals(lines, st.period_start)
    return StatementSummaryOut(
        id=st.id,
        period_start=st.period_start,
        period_end=st.period_end,
        due_date=st.due_date,
        minimum_payment=st.minimum_payment,
        total_payment=st.total_payment,
        purchases_total=purchases,
        payments_total=payments,
        lines_count=len(lines),
    )


@router.get("", response_model=list[CardOut])
async def list_cards(current_user: CurrentUser, db: DbSession) -> list[CardOut]:
    tz = user_tz()
    debts = (
        (
            await db.execute(
                select(Debt)
                .where(Debt.user_id == current_user.id, Debt.email_format.is_not(None))
                .order_by(Debt.created_at)
            )
        )
        .scalars()
        .all()
    )
    if not debts:
        return []
    debt_ids = [d.id for d in debts]

    statements = (
        (
            await db.execute(
                select(SavedStatement)
                .where(SavedStatement.debt_id.in_(debt_ids))
                .order_by(SavedStatement.period_end.desc())
            )
        )
        .scalars()
        .all()
    )
    lines_by_statement: dict[uuid.UUID, list[SavedStatementLine]] = defaultdict(list)
    if statements:
        for line in (
            (
                await db.execute(
                    select(SavedStatementLine)
                    .where(SavedStatementLine.statement_id.in_([s.id for s in statements]))
                    .order_by(SavedStatementLine.position)
                )
            )
            .scalars()
            .all()
        ):
            lines_by_statement[line.statement_id].append(line)

    cutoffs = [d.statement_at for d in debts if d.statement_at is not None]
    movements = []
    if cutoffs:
        movements = (
            await db.execute(
                select(
                    Transaction.id,
                    Transaction.debt_id,
                    Transaction.occurred_at,
                    Transaction.merchant,
                    Transaction.category,
                    Transaction.amount,
                    Transaction.transaction_type,
                )
                .where(
                    Transaction.user_id == current_user.id,
                    Transaction.debt_id.in_(debt_ids),
                    Transaction.source == "card",
                    Transaction.occurred_at >= min(cutoffs),
                )
                .order_by(Transaction.occurred_at.desc())
            )
        ).all()

    out = []
    for d in debts:
        own = [s for s in statements if s.debt_id == d.id]
        latest = own[0] if own else None
        since = [
            m for m in movements
            if m.debt_id == d.id and d.statement_at is not None and m.occurred_at >= d.statement_at
        ]
        purchases = [m for m in since if m.transaction_type is TransactionType.debit]
        paid = sum((m.amount for m in since if m.transaction_type is TransactionType.credit), ZERO)
        bought = sum((m.amount for m in purchases), ZERO)
        installments = d.next_installments or ZERO
        limit = latest.credit_limit if latest else None
        # The cut-off is the day before the first instant of the new cycle.
        cutoff = latest.period_end if latest else (
            d.statement_at.astimezone(tz).date() if d.statement_at else None
        )
        out.append(
            CardOut(
                debt_id=d.id,
                name=d.bank_name,
                balance=d.total_amount,
                credit_limit=limit,
                available=max(limit - d.total_amount, ZERO) if limit is not None else None,
                minimum_payment=d.minimum_payment,
                payment_due_date=d.payment_due_date,
                paid_since_cutoff=paid,
                cutoff_date=cutoff,
                next_cutoff_date=add_month(cutoff) if cutoff else None,
                next_due_date=add_month(d.payment_due_date) if d.payment_due_date else None,
                purchases_since_cutoff=[
                    CardPurchaseOut(
                        id=m.id,
                        occurred_at=m.occurred_at,
                        merchant=m.merchant,
                        category=m.category,
                        amount=m.amount,
                    )
                    for m in purchases
                ],
                purchases_since_cutoff_total=bought,
                next_installments=installments,
                next_statement_estimate=bought + installments,
                installment_plans=[
                    InstallmentPlanOut(**vars(p))
                    for p in installment_plans(lines_by_statement[latest.id] if latest else [])
                ],
                statements=[_summary(s, lines_by_statement[s.id]) for s in own],
            )
        )
    return out


@router.get("/{debt_id}/statements/{statement_id}", response_model=StatementDetailOut)
async def get_statement(
    debt_id: uuid.UUID, statement_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> StatementDetailOut:
    st = (
        await db.execute(
            select(SavedStatement).where(
                SavedStatement.id == statement_id,
                SavedStatement.debt_id == debt_id,
                SavedStatement.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if st is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Statement not found")
    lines = list(
        (
            await db.execute(
                select(SavedStatementLine)
                .where(SavedStatementLine.statement_id == st.id)
                .order_by(SavedStatementLine.position)
            )
        )
        .scalars()
        .all()
    )
    return StatementDetailOut(
        **_summary(st, lines).model_dump(),
        lines=[
            StatementLineOut(
                position=line.position,
                posted_on=line.posted_on,
                description=line.description,
                amount=line.amount,
                billed=line.billed,
                installment=line.installment,
                installments=line.installments,
                pending=line.pending,
            )
            for line in lines
        ],
    )
