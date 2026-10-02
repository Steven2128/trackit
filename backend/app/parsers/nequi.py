"""Parser for Nequi (Colombia) movement notification emails.

Senders: notificaciones@nequi.com.co (Bre-B) and somos@nequi.com.co (PSE and
bill payments — it also sends login notices and onboarding mail, which match
no template and return None). Marketing from somos@notificaciones.nequi.com.co
is rejected by ``can_parse``.

Supported templates:

1. Recibiste ("¡Recibiste plata por Bre-B!")
   "Recibiste 15.000 de <SENDER NAME> el 3 de julio de 2026 a las 3:07 p.m,
    desde el banco <BANK>."
   → credit, merchant = "Nequi", category = "transfer". Nequi is a parking
   destination (PARSERS.md): money arriving there is never real income for
   the app's totals, so every inbound credit is tagged "transfer" up front —
   not only the ones the matcher later pairs. When <BANK> is Itaú or
   Davivienda it's also flagged ``is_pairing_candidate=True`` so the matcher
   can link it to that bank's outbound debit.

2. Enviaste ("¡Enviaste plata por Bre-B!")
   "Enviaste de manera exitosa 23.000 a la llave @<KEY> de <RECIPIENT> el
    30 de junio de 2026 a las 8:45 p.m."
   → debit, merchant = <RECIPIENT>. Real outflow from the Nequi balance —
   NOT a pairing candidate.

3. Pago exitoso ("¡Pago exitoso!", PSE from Nequi)
   "Hiciste un pago en <MERCHANT> por $92.990 Fecha: El 6 de abril de 2026
    Hora: 2:28 p. m. CUS: ..."
   → debit, merchant = <MERCHANT>.

4. Comprobante de factura ("Comprobante de pago Enel", "Tu comprobante de
   pago Claro Hogar")
   "Listo tu pago en <BILLER> Pagaste con Nequi tu factura por $92.670 ...
    Fecha del pago: 06/Ago/2026"
   → debit, merchant = <BILLER>. The body has no time, so occurred_at is the
   email's received time (sent the moment the bill is paid).

Format gotchas (differ from Itaú):
- Amounts use Colombian formatting: dot = thousands, optional comma =
  decimals, no "$" sign ("1.647.000").
- Dates are Spanish long form in Bogotá local time, 12h clock, and the
  article is "a las" except at one o'clock where it's "a la 1:55 p.m".
  Pago exitoso splits it instead: "El 6 de abril de 2026 Hora: 2:28 p. m."
- Payment templates prefix the amount with "$"; Bre-B ones don't.
"""

from __future__ import annotations

import html as html_lib
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models.transaction import TransactionType
from app.parsers.base import EmailEnvelope, EmailParser, ParsedTransaction

NEQUI_SENDER = "notificaciones@nequi.com.co"
NEQUI_PAYMENTS_SENDER = "somos@nequi.com.co"

# Source banks whose outbound debits the matcher can pair with a Recibiste.
_SELF_TRANSFER_BANKS = ("itau", "davivienda")

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

# "El 6 de abril de 2026 Hora: 2:28 p. m."
_PAGO_DATETIME_RE = re.compile(
    r"El\s+(?P<day>\d{1,2})\s+de\s+(?P<month>[a-záéíóú]+)\s+de\s+(?P<year>\d{4})"
    r"\s+Hora\s*:\s*(?P<hour>\d{1,2}):(?P<minute>\d{2})\s*(?P<meridiem>[ap])\.?\s*m",
    re.IGNORECASE,
)

_PAGO_RE = re.compile(
    rf"Hiciste\s+un\s+pago\s+en\s+(?P<merchant>.+?)\s+por\s+\$\s*{_AMOUNT}",
    re.IGNORECASE,
)

_FACTURA_RE = re.compile(
    rf"Listo\s+tu\s+pago\s+en\s+(?P<merchant>.+?)\s+Pagaste\s+con\s+Nequi"
    rf"\s+tu\s+factura\s+por\s+\$\s*{_AMOUNT}",
    re.IGNORECASE,
)

_ENVIASTE_RE = re.compile(
    rf"Enviaste\s+de\s+manera\s+exitosa\s+{_AMOUNT}"
    r"\s+a\s+la\s+llave\s+\S+\s+de\s+(?P<recipient>.+?)\s+el\s+\d",
    re.IGNORECASE,
)


class NequiParser(EmailParser):
    name = "nequi"
    sender_filter = (NEQUI_SENDER, NEQUI_PAYMENTS_SENDER)

    def can_parse(self, envelope: EmailEnvelope) -> bool:
        sender = envelope.sender.lower()
        return NEQUI_SENDER in sender or NEQUI_PAYMENTS_SENDER in sender

    def parse(self, envelope: EmailEnvelope) -> ParsedTransaction | None:
        if not envelope.html_body:
            return None

        text = self._normalize_html(envelope.html_body)

        # 3-4. PSE / bill payments — own date formats, checked first.
        payment = self._parse_payment(envelope, text)
        if payment is not None:
            return payment

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
                # Parking destination: inbound Nequi money never counts as
                # received income, paired or not.
                category="transfer",
                currency="COP",
                raw_email_reference=envelope.message_id,
                # Money arriving from the user's own Itaú/Davivienda is a
                # self-transfer the matcher should pair; anything else stays
                # an unpaired transfer.
                is_pairing_candidate=any(
                    b in bank.lower() for b in _SELF_TRANSFER_BANKS
                ),
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

    @classmethod
    def _parse_payment(cls, envelope: EmailEnvelope, text: str) -> ParsedTransaction | None:
        pago = _PAGO_RE.search(text)
        if pago:
            occurred_at = cls._extract_datetime(text, _PAGO_DATETIME_RE)
        else:
            pago = _FACTURA_RE.search(text)
            occurred_at = envelope.received_at.astimezone(timezone.utc) if pago else None
        if pago is None or occurred_at is None:
            return None
        amount = cls._parse_amount(pago.group("amount"))
        if amount is None:
            return None
        return ParsedTransaction(
            amount=amount,
            transaction_type=TransactionType.debit,
            occurred_at=occurred_at,
            merchant=pago.group("merchant").strip(),
            category=None,
            currency="COP",
            raw_email_reference=envelope.message_id,
        )

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

    @staticmethod
    def _extract_datetime(text: str, pattern: re.Pattern[str] = _DATETIME_RE) -> datetime | None:
        match = pattern.search(text)
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
