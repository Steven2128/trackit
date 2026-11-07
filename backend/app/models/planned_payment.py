import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PlannedPayment(Base):
    """A recurring monthly obligation (rent, debt installment, utilities).

    One table serves three roadmap features: committed money ("apartado" —
    amounts subtracted from the calculated available), due-date reminders
    (`due_day` + `grace_days` define the real deadline), and the pay-first
    checklist (obligations listed in priority order on payday).
    `is_debt_payment` sorts debts first in that checklist.
    """

    __tablename__ = "planned_payments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    due_day: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-31
    grace_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    is_debt_payment: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    # "YYYY-MM" (local month) when the user last checked this off in the
    # monthly plan. Comparing against the current month makes the check
    # reset itself when a new month starts — no cron needed.
    paid_month: Mapped[str | None] = mapped_column(String(7), nullable=True)
    # One-off obligation (money owed to a friend): due once on this date,
    # due_day is then ignored. NULL = recurring every month on due_day.
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Recurring every N months (water: every 2). Due only in months that are
    # a multiple of N away from ``first_month`` ("YYYY-MM"); NULL anchor =
    # the month it was created.
    every_months: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    first_month: Mapped[str | None] = mapped_column(String(7), nullable=True)
    # The bill changes every time (utilities): ``amount`` is an estimate.
    amount_varies: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    # Share of the bill someone else pays back (50 = half). The user still
    # pays it all on the due date; it only tells them what to collect.
    shared_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
