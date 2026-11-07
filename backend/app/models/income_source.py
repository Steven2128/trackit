import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IncomeSource(Base):
    """One expected recurring deposit per row — a biweekly salary is two rows
    (day 5 and day 20), a monthly bonus a third. `expected_day` is the day of
    month the money usually lands; payments that fall on weekends drift a few
    days, so consumers should match with tolerance."""

    __tablename__ = "income_sources"

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
    expected_day: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-31
    # Can be paid early, from this day of the previous month (the bonus is
    # due in the first 5 business days but sometimes lands after the 20th).
    # NULL = only a few days before expected_day.
    early_from_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
