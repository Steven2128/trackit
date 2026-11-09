import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TransactionType(str, enum.Enum):
    debit = "debit"
    credit = "credit"


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # NULL for movements the user typed in (cash expenses).
    provider_connection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("provider_connections.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    merchant: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    transaction_type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType, name="transaction_type"), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    card_last_digits: Mapped[str | None] = mapped_column(String(4), nullable=True)
    # User-written free-text note ("qué fue este gasto") — never parsed.
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_email_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_pairing_candidate: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    transfer_pair_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    # Which account the money moved in: the parser name for bank emails
    # ("davivienda", "nequi", "itau_co"), "card" for credit-card emails and
    # "cash" for typed-in cash expenses. Drives account balances (net_worth).
    # NULL on rows synced before the column existed.
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Part of a debit someone else covers (the brother's half of a shared
    # bill): spending counts only amount - shared_amount, while the account
    # still drops by the full amount. Their payback arrives as a credit with
    # category "reimbursement", which isn't income. NULL = not shared.
    shared_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    # Credit-card movement (purchase or card payment) read from the card's
    # email sender — see Debt.email_sender.
    debt_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("debts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Who a shared expense, a payback or an expense they paid is with — see
    # services/contact_balance.py. source="contact" marks an expense the
    # contact paid: no account of the user moves, only their part counts.
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    @property
    def manual(self) -> bool:
        """Typed in by the user (no email behind it): amount, date and
        deletion are editable."""
        return self.provider_connection_id is None and self.raw_email_reference is None

    __table_args__ = (
        Index(
            "ix_transactions_pairing_candidate",
            "user_id",
            "is_pairing_candidate",
            "occurred_at",
            postgresql_where=text(
                "is_pairing_candidate IS TRUE AND transfer_pair_id IS NULL"
            ),
        ),
        # Dedupe guard used by email_sync; created in migration
        # f1a3c2d4e5b6. Declared here so autogenerate doesn't drop it.
        Index(
            "ix_transactions_provider_email_uniq",
            "provider_connection_id",
            "raw_email_reference",
            unique=True,
            postgresql_where=text("raw_email_reference IS NOT NULL"),
        ),
    )


# The user's own part of a movement — what spending sums add up. Equals
# ``amount`` unless the expense is shared (see Transaction.shared_amount).
OWN_AMOUNT = Transaction.amount - func.coalesce(Transaction.shared_amount, 0)
