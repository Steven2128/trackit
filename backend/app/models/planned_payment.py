import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, func
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
