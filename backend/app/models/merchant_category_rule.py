import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MerchantCategoryRule(Base):
    """User rule: merchants containing `pattern` go to `category`.

    Applied by email_sync before the built-in rules (services/categorizer.py),
    so "TIENDA D1 …" lands in the user's "mercado" instead of the system's
    "food". `pattern` is stored normalized (lowercase, no accents, words
    separated by single spaces) and matched as whole words.
    """

    __tablename__ = "merchant_category_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pattern: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "pattern", name="uq_merchant_category_rules_user_pattern"),
    )
