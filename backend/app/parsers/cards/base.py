"""Credit-card email formats.

Unlike bank parsers (app/parsers/*.py), card parsers are not bound to a
sender: the user links a sender to a Debt from the app and picks one of these
formats. A card email yields one CardEvent:

- purchase  → spending on the card; raises the debt balance.
- payment   → the user paid the card; lowers the balance. The bank debit that
              funded it is re-tagged "debt_payment" by the matcher.
- statement → refreshes minimum payment and due date; no transaction.
"""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from app.parsers.base import EmailEnvelope


class CardEventKind(str, enum.Enum):
    purchase = "purchase"
    payment = "payment"
    statement = "statement"


@dataclass
class CardEvent:
    kind: CardEventKind
    occurred_at: datetime
    amount: Decimal | None = None
    merchant: str | None = None
    card_last_digits: str | None = None
    minimum_payment: Decimal | None = None
    payment_due_date: date | None = None


class CardEmailParser(ABC):
    key: str = "base"
    label: str = "base"
    # Pre-filled in the app when the user picks this format.
    default_sender: str | None = None

    @abstractmethod
    def parse(self, envelope: EmailEnvelope) -> CardEvent | None:
        """Extract the card event, or None for non-movement mail (marketing)."""
