from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from app.models.transaction import TransactionType


@dataclass
class EmailAttachment:
    """Metadata for one attachment part — bytes are fetched lazily via
    `GmailClient.get_attachment(message_id, attachment_id)`, since Gmail
    returns attachment data as a separate API call."""

    filename: str
    mime_type: str
    attachment_id: str
    size: int


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
    attachments: list[EmailAttachment] = field(default_factory=list)


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
    is_pairing_candidate: bool = False


class EmailParser(ABC):
    """Base class for bank-specific email parsers."""

    name: str = "base"
    # Gmail `from:` address(es) the sync query must include for this parser.
    sender_filter: str | tuple[str, ...] | None = None

    @abstractmethod
    def can_parse(self, envelope: EmailEnvelope) -> bool:
        """Cheap predicate to decide whether this parser handles the message."""

    @abstractmethod
    def parse(self, envelope: EmailEnvelope) -> ParsedTransaction | None:
        """Extract a transaction from the envelope, or `None` if it shouldn't yield one."""
