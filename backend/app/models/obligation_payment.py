import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Numeric, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ObligationPayment(Base):
    """Money put toward one due date of a planned payment or a debt: the
    rent of the 24-Oct cycle, the 5-Nov card installment. Several rows add
    up (partial payments); a row for a future due date is paying ahead.

    Due dates are not stored — they're computed from the planned payment or
    debt (services/cash_position_sources.py) — so a payment points at its
    parent plus the ``due_date`` it pays. ``transaction_id`` is the cash
    expense created when it was paid in cash (the balance has to drop with
    it); bank payments arrive by email on their own.
    """

    __tablename__ = "obligation_payments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    planned_payment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("planned_payments.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    debt_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("debts.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    paid_on: Mapped[date] = mapped_column(Date, nullable=False)
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "(planned_payment_id IS NULL) <> (debt_id IS NULL)",
            name="ck_obligation_payments_one_parent",
        ),
    )
