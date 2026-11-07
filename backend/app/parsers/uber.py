"""Parser for Uber trip receipts.

Sender: noreply@uber.com ("Recibos de Uber" / "Uber Receipts").
Subjects: "Tu viaje del jueves por la noche con Uber", "Tu viaje Uber del
sábado por la tarde", "Your Friday afternoon trip with Uber". Spanish and
English bodies use the same layout:

   "Total COP 4,969 ... Pagos Mastercard ••••6017 (Davivienda) COP 4,969
    05/11/26 7:43 p.m. ... Detalles del viaje Moto 2.59 kilómetros"
   "Total COP 6,903 ... Payments Cash COP 6,903 10/1/26 2:27 AM ...
    Trip details UberYa 3.44 kilometers"

The payment method decides which account the trip comes out of:

- "Cash" / "Efectivo" → ``source="cash"``: a cash expense, like the ones
  the user types in.
- A Davivienda card ("(Davivienda)") → ``source="uber"``: Davivienda
  doesn't always email card charges this small. Counts against the
  Davivienda balance, and ``transfer_matcher.reconcile_receipts`` folds it
  into the bank debit if that email shows up.
- Any other card → None: a credit card's own email already records it.

Amounts use US formatting ("COP 4,969"). The receipt arrives when the
trip is paid, so ``occurred_at`` is the email's arrival time (the body's
date is day/month in Spanish and month/day in English).
"""

from __future__ import annotations

import html as html_lib
import re
from decimal import Decimal

from app.models.transaction import TransactionType
from app.parsers.base import EmailEnvelope, EmailParser, ParsedTransaction

UBER_SENDER = "noreply@uber.com"
# Receipt source for trips paid with the Davivienda card.
UBER_CARD_SOURCE = "uber"

_TRIP_SUBJECT_RE = re.compile(r"\b(viaje|trip)\b", re.IGNORECASE)
_TOTAL_RE = re.compile(r"\bTotal\s+COP\s*(?P<amount>[\d,]+(?:\.\d+)?)", re.IGNORECASE)
_PAYMENT_RE = re.compile(
    r"\b(?:Pagos|Payments)\s+(?P<method>.+?)\s+COP\s*[\d,]", re.IGNORECASE
)
_CARD_DIGITS_RE = re.compile(r"(\d{4})\b")
_PRODUCT_RE = re.compile(
    r"(?:Detalles del viaje|Trip details)\s+(?P<product>.+?)\s+\d+(?:\.\d+)?\s+(?:kil|mi)",
    re.IGNORECASE,
)


class UberParser(EmailParser):
    name = "uber"
    sender_filter = UBER_SENDER

    def can_parse(self, envelope: EmailEnvelope) -> bool:
        return UBER_SENDER in envelope.sender.lower()

    def parse(self, envelope: EmailEnvelope) -> ParsedTransaction | None:
        body = envelope.html_body or envelope.text_body
        if not body or not _TRIP_SUBJECT_RE.search(envelope.subject):
            return None
        text = _normalize(body)

        total = _TOTAL_RE.search(text)
        payment = _PAYMENT_RE.search(text)
        if total is None or payment is None:
            return None
        try:
            amount = Decimal(total.group("amount").replace(",", ""))
        except Exception:
            return None
        if amount <= 0:
            return None

        method = payment.group("method").strip()
        lowered = method.lower()
        if lowered in ("cash", "efectivo"):
            source, digits = "cash", None
        elif "davivienda" in lowered:
            card = _CARD_DIGITS_RE.search(method)
            source, digits = UBER_CARD_SOURCE, card.group(1) if card else None
        else:
            return None  # another card: its own email records the charge

        product = _PRODUCT_RE.search(text)
        name = product.group("product").strip() if product else ""
        # "UberYa" → "Uber Ya": the categorizer matches "uber" as a word.
        if name.lower().startswith("uber"):
            name = name[4:]
        merchant = f"Uber {name}".strip()
        return ParsedTransaction(
            amount=amount,
            transaction_type=TransactionType.debit,
            occurred_at=envelope.received_at,
            merchant=merchant,
            currency="COP",
            card_last_digits=digits,
            raw_email_reference=envelope.message_id,
            source=source,
        )


def _normalize(body: str) -> str:
    no_style = re.sub(r"<(style|script)\b.*?</\1>", " ", body, flags=re.IGNORECASE | re.DOTALL)
    no_tags = re.sub(r"<[^>]+>", " ", no_style)
    return re.sub(r"\s+", " ", html_lib.unescape(no_tags)).strip()
