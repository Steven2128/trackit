import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AccountKind(str, enum.Enum):
    """Where the user's money sits. Each kind maps to the transaction
    ``source`` whose movements move its balance (see services/net_worth.py)."""

    davivienda = "davivienda"
    nequi = "nequi"
    cash = "cash"


class Account(Base):
    """A money account tracked for net worth.

    Emails never carry balances, so the balance is computed, not stored:
    opening_balance (typed by the user at opening_at) + credits − debits of
    the account's movements after opening_at + reconciliation adjustments.
    """

    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[AccountKind] = mapped_column(
        Enum(AccountKind, name="account_kind"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    opening_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (UniqueConstraint("user_id", "kind", name="uq_accounts_user_kind"),)


class AccountAdjustment(Base):
    """Reconciliation: the user typed the real balance and it differed from
    the computed one. ``amount`` is the signed difference (real − computed)
    — money that moved without an email (cash, interest, fees). Visible in
    the app, never counted as categorized spending."""

    __tablename__ = "account_adjustments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    reported_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
