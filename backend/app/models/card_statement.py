import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SavedStatement(Base):
    """One monthly statement of a credit card, as read from its PDF
    (app/parsers/cards/rappicard_statement.py). Kept so the app can show
    each statement with its movements and how far along every purchase in
    installments is. One row per card and cut-off day."""

    __tablename__ = "card_statements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    debt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("debts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    # The cut-off day.
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    minimum_payment: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    # The whole balance at the cut-off, unbilled installments included.
    total_payment: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    credit_limit: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("debt_id", "period_end", name="uq_card_statements_debt_period_end"),
    )


class SavedStatementLine(Base):
    """A movement of a statement: a purchase (with its installment "n of N"
    and the capital still to bill) or a payment (negative amount)."""

    __tablename__ = "card_statement_lines"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    statement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("card_statements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    posted_on: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    billed: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    installment: Mapped[int | None] = mapped_column(Integer, nullable=True)
    installments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pending: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
