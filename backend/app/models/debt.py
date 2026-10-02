import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Debt(Base):
    __tablename__ = "debts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bank_name: Mapped[str] = mapped_column(String(128), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    interest_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    minimum_payment: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    # Credit-card email link, configured from the app (no sender hardcoded):
    # emails from `email_sender` are read with the `email_format` template
    # (app/parsers/cards) — purchases raise total_amount, payments lower it,
    # statements refresh minimum_payment / payment_due_date.
    email_sender: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_format: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Purchases on other cards from the same sender are ignored when set.
    card_last_digits: Mapped[str | None] = mapped_column(String(4), nullable=True)
    payment_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Only movements after this instant touch total_amount: the user enters the
    # current balance when linking, and older emails would double-count it.
    email_linked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
