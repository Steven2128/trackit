"""Parser for Nequi (Colombia) Bre-B notification emails.

Sender: notificaciones@nequi.com.co (transactional). Marketing comes from
somos@nequi.com.co / somos@notificaciones.nequi.com.co and is rejected by
``can_parse``.

Supported templates:

1. Recibiste ("¡Recibiste plata por Bre-B!")
   "Recibiste 15.000 de <SENDER NAME> el 3 de julio de 2026 a las 3:07 p.m,
    desde el banco <BANK>."
   → credit, merchant = "Nequi". When <BANK> is Itaú this is (almost always)
   the user moving their own money out of Itaú, so it's flagged
   ``is_pairing_candidate=True`` for the transfer matcher. Money from any
   other bank is treated as income from a third party.

2. Enviaste ("¡Enviaste plata por Bre-B!")
   "Enviaste de manera exitosa 23.000 a la llave @<KEY> de <RECIPIENT> el
    30 de junio de 2026 a las 8:45 p.m."
   → debit, merchant = <RECIPIENT>. Real outflow from the Nequi balance —
   NOT a pairing candidate.

Format gotchas (differ from Itaú):
- Amounts use Colombian formatting: dot = thousands, optional comma =
  decimals, no "$" sign ("1.647.000").
- Dates are Spanish long form in Bogotá local time, 12h clock, and the
  article is "a las" except at one o'clock where it's "a la 1:55 p.m".
"""

from __future__ import annotations

import html as html_lib
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models.transaction import TransactionType
from app.parsers.base import EmailEnvelope, EmailParser, ParsedTransaction

NEQUI_SENDER = "notificaciones@nequi.com.co"

# Colombia is UTC-5 year-round (no DST).
COLOMBIA_TZ = timezone(timedelta(hours=-5))

_MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

# "el 3 de julio de 2026 a las 3:07 p.m" / "el 1 de julio de 2026 a la 1:55 p.m"
_DATETIME_RE = re.compile(
    r"el\s+(?P<day>\d{1,2})\s+de\s+(?P<month>[a-záéíóú]+)\s+de\s+(?P<year>\d{4})"
    r"\s+a\s+las?\s+(?P<hour>\d{1,2}):(?P<minute>\d{2})\s*(?P<meridiem>[ap])\.?m",
    re.IGNORECASE,
)

# Colombian amount: dot thousands, optional comma decimals ("1.647.000", "15.000,50")
_AMOUNT = r"(?P<amount>\d{1,3}(?:\.\d{3})*(?:,\d+)?)"

_RECIBISTE_RE = re.compile(
    rf"Recibiste\s+{_AMOUNT}\s+de\s+(?P<sender_name>.+?)\s+el\s+\d",
    re.IGNORECASE,
)

_SOURCE_BANK_RE = re.compile(
    r"desde\s+el\s+banco\s+(?P<bank>[^.,]+)",
    re.IGNORECASE,
)

_ENVIASTE_RE = re.compile(
    rf"Enviaste\s+de\s+manera\s+exitosa\s+{_AMOUNT}"
    r"\s+a\s+la\s+llave\s+\S+\s+de\s+(?P<recipient>.+?)\s+el\s+\d",
    re.IGNORECASE,
)


class NequiParser(EmailParser):
    name = "nequi"
    sender_filter = NEQUI_SENDER

    def can_parse(self, envelope: EmailEnvelope) -> bool:
        return NEQUI_SENDER in envelope.sender.lower()

    def parse(self, envelope: EmailEnvelope) -> ParsedTransaction | None:
        if not envelope.html_body:
            return None

        text = self._normalize_html(envelope.html_body)

        occurred_at = self._extract_datetime(text)
        if occurred_at is None:
            return None

        # 1. Recibiste (incoming credit)
        recibiste = _RECIBISTE_RE.search(text)
        if recibiste:
            amount = self._parse_amount(recibiste.group("amount"))
            if amount is None:
                return None
            bank_match = _SOURCE_BANK_RE.search(text)
            bank = bank_match.group("bank").strip() if bank_match else ""
            return ParsedTransaction(
                amount=amount,
                transaction_type=TransactionType.credit,
                occurred_at=occurred_at,
                merchant="Nequi",
                category=None,
                currency="COP",
                raw_email_reference=envelope.message_id,
                # Money arriving from the user's own Itaú is a self-transfer
                # the matcher should pair; anything else is third-party income.
                is_pairing_candidate="itau" in bank.lower(),
            )

        # 2. Enviaste (outgoing debit)
        enviaste = _ENVIASTE_RE.search(text)
        if enviaste:
            amount = self._parse_amount(enviaste.group("amount"))
            if amount is None:
                return None
            return ParsedTransaction(
                amount=amount,
                transaction_type=TransactionType.debit,
                occurred_at=occurred_at,
                merchant=enviaste.group("recipient").strip(),
                category=None,
                currency="COP",
                raw_email_reference=envelope.message_id,
            )

        return None

    @staticmethod
    def _normalize_html(html_body: str) -> str:
        """Decode HTML entities, strip tags, collapse whitespace."""
        decoded = html_lib.unescape(html_body)
        no_tags = re.sub(r"<[^>]+>", " ", decoded)
        return re.sub(r"\s+", " ", no_tags).strip()

    @staticmethod
    def _parse_amount(raw: str) -> Decimal | None:
        try:
            return Decimal(raw.replace(".", "").replace(",", "."))
        except Exception:
            return None

    @classmethod
    def _extract_datetime(cls, text: str) -> datetime | None:
        match = _DATETIME_RE.search(text)
        if not match:
            return None
        month = _MONTHS.get(match.group("month").lower())
        if month is None:
            return None
        hour = int(match.group("hour")) % 12
        if match.group("meridiem").lower() == "p":
            hour += 12
        try:
            naive = datetime(
                int(match.group("year")),
                month,
                int(match.group("day")),
                hour,
                int(match.group("minute")),
            )
        except ValueError:
            return None
        return naive.replace(tzinfo=COLOMBIA_TZ).astimezone(timezone.utc)
