from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.models.transaction import TransactionType


@dataclass
class EmailEnvelope:
    """Normalized representation of a single email passed to parsers.

    Parsers receive this dataclass — they don't care whether the email came
    from Gmail's REST API or from a local .eml fixture. The Gmail integration
    layer builds these envelopes from the API response; tests build them from
    .eml files via `tests/_helpers.py`.
    """

    sender: str
    subject: str
    message_id: str
    received_at: datetime
    html_body: str | None = None
    text_body: str | None = None


@dataclass
class ParsedTransaction:
    amount: Decimal
    transaction_type: TransactionType
    occurred_at: datetime
    merchant: str | None = None
    category: str | None = None
    currency: str = "USD"
    card_last_digits: str | None = None
    raw_email_reference: str | None = None


class EmailParser(ABC):
    """Base class for bank-specific email parsers."""

    name: str = "base"
    sender_filter: str | None = None

    @abstractmethod
    def can_parse(self, envelope: EmailEnvelope) -> bool:
        """Cheap predicate to decide whether this parser handles the message."""

    @abstractmethod
    def parse(self, envelope: EmailEnvelope) -> ParsedTransaction | None:
        """Extract a transaction from the envelope, or `None` if it shouldn't yield one."""
