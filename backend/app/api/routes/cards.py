"""Credit cards: balance, the statement to pay, the one being built, the
purchases in installments and every saved statement with its movements.

A card is a debt with a card format: linked to the card's emails, or read
only from statements the user uploads (Banco de Bogotá). Computed on the
fly from the debt, its saved statements (card_statements) and its movements.
"""

import asyncio
import uuid
from collections import defaultdict
from decimal import Decimal

from fastapi import APIRouter, File, HTTPException, UploadFile, status
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
from app.core.config import settings
from app.parsers.cards import bancodebogota_statement, rappicard_statement
from app.parsers.cards.rappicard_statement import CardStatement
from app.schemas.card import StatementUploadOut
from app.services.card_statement import (
    apply_card_statement,
    card_movement_clause,
    is_card_payment,
)
from app.services.email_sync import load_user_rules
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
                    card_movement_clause(debts),
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
        purchases = [m for m in since if not is_card_payment(m.transaction_type, m.category)]
        paid = sum(
            (m.amount for m in since if is_card_payment(m.transaction_type, m.category)), ZERO
        )
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


# Statement readers by card format; an upload to a debt with no format yet
# tries them in order and the one that reads it sets the format.
_STATEMENT_READERS = {
    "bancodebogota": bancodebogota_statement.extract_statement,
    "rappicard": rappicard_statement.extract_statement,
}
MAX_STATEMENT_BYTES = 10 * 1024 * 1024


def _read_statement(pdf: bytes, fmt: str | None) -> tuple[str, CardStatement] | None:
    passwords = [None, settings.rappicard_statement_pdf_password,
                 settings.itau_statement_pdf_password]
    formats = [fmt] if fmt in _STATEMENT_READERS else list(_STATEMENT_READERS)
    for key in formats:
        for password in dict.fromkeys(passwords):
            try:
                statement = _STATEMENT_READERS[key](pdf, password)
            except Exception:  # noqa: BLE001 — locked, wrong password, not a PDF
                continue
            if statement is not None:
                return key, statement
    return None


@router.post("/{debt_id}/statement", response_model=StatementUploadOut)
async def upload_statement(
    debt_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    file: UploadFile = File(...),
) -> StatementUploadOut:
    """Read a card statement PDF the user uploads (cards whose bank doesn't
    email it, like Banco de Bogotá) and apply it like an emailed one: cut-off,
    installments, missing purchases, balance, minimum and due date. The
    debt becomes a card if it wasn't."""
    debt = (
        await db.execute(select(Debt).where(Debt.id == debt_id, Debt.user_id == current_user.id))
    ).scalar_one_or_none()
    if debt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="debt_not_found")
    pdf = await file.read(MAX_STATEMENT_BYTES + 1)
    if len(pdf) > MAX_STATEMENT_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="too_large")
    read = await asyncio.to_thread(_read_statement, pdf, debt.email_format)
    if read is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="statement_unreadable"
        )
    fmt, statement = read
    if debt.email_format is None:
        debt.email_format = fmt
    # The PDF is the authority for what to pay now.
    if statement.minimum_payment is not None:
        debt.minimum_payment = statement.minimum_payment
    if statement.due_date is not None:
        debt.payment_due_date = statement.due_date
    rules = await load_user_rules(db, current_user.id)
    inserted = await apply_card_statement(db, None, debt, statement, rules)
    await db.commit()
    return StatementUploadOut(
        card_format=fmt,
        period_end=statement.period_end,
        due_date=statement.due_date,
        minimum_payment=statement.minimum_payment,
        total_payment=statement.total_payment,
        balance=debt.total_amount,
        purchases_added=inserted,
        lines=len(statement.lines),
    )
