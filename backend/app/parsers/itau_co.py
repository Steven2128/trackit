"""Parser for Itaú Colombia transaction notification emails.

Sender: notificaciones@clienteitau.co
Subject (always the same): "Notificaciones Itau" — we cannot use it to
discriminate template type; the body text decides.

Supported templates:

1. Compra (purchase with card)
   "Se realizó una compra en <MERCHANT> desde tu (Cuenta de Ahorros|Tarjeta Credito) número *****<DIGITS>"
   → debit, merchant = <MERCHANT>

2. Depósito (incoming credit, e.g. payroll)
   "Se realizó un depósito a tu Cuenta de Ahorros número ***<DIGITS>"
   → credit, merchant = None

3. Débito por canal (outgoing debit without merchant info)
   "Se realizó un Débito de tu Cuenta de Ahorros número ***<DIGITS> ... Canal: <CHANNEL>"
   → debit, merchant = <CHANNEL>  (e.g. "Portal Internet")
   These need to be paired with incoming notifications from Nequi/Daviplata/
   Falabella to classify them as `category="transfer"`. See PARSERS.md.

Any email matching the Itaú sender that does not match any of the templates
above (e.g. marketing emails, plan updates) returns None and is logged by the
dispatcher as `parser_skipped`.
"""

from __future__ import annotations

import html as html_lib
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models.transaction import TransactionType
from app.parsers.base import EmailEnvelope, EmailParser, ParsedTransaction

ITAU_CO_SENDER = "notificaciones@clienteitau.co"

# Colombia is UTC-5 year-round (no DST).
COLOMBIA_TZ = timezone(timedelta(hours=-5))


class ItauCoParser(EmailParser):
    name = "itau_co"
    sender_filter = ITAU_CO_SENDER

    _AMOUNT_RE = re.compile(r"Monto\s*:\s*\$([\d,]+(?:\.\d+)?)")
    _DATETIME_RE = re.compile(
        r"Fecha y hora\s*:\s*(\d{4}/\d{2}/\d{2})\s+(\d{2}:\d{2}:\d{2})"
    )

    _PURCHASE_RE = re.compile(
        r"compra\s+en\s+(?P<merchant>.+?)"
        r"\s+desde\s+tu\s+(?P<instrument>Cuenta de Ahorros|Tarjeta Credito)"
        r"\s+número\s+\*+(?P<digits>\d{3,})",
        re.IGNORECASE,
    )

    _DEPOSIT_RE = re.compile(
        r"depósito\s+a\s+tu\s+Cuenta de Ahorros\s+número\s+\*+(?P<digits>\d{3,})",
        re.IGNORECASE,
    )

    _DEBIT_RE = re.compile(
        r"Débito\s+de\s+tu\s+Cuenta de Ahorros\s+número\s+\*+(?P<digits>\d{3,})",
        re.IGNORECASE,
    )

    _CHANNEL_RE = re.compile(
        r"Canal\s*:\s*(?P<channel>.+?)\s+Fecha y hora",
        re.IGNORECASE,
    )

    def can_parse(self, envelope: EmailEnvelope) -> bool:
        return ITAU_CO_SENDER in envelope.sender.lower()

    def parse(self, envelope: EmailEnvelope) -> ParsedTransaction | None:
        if not envelope.html_body:
            return None

        text = self._normalize_html(envelope.html_body)

        amount = self._extract_amount(text)
        occurred_at = self._extract_datetime(text)
        if amount is None or occurred_at is None:
            return None

        # 1. Compra (purchase)
        purchase = self._PURCHASE_RE.search(text)
        if purchase:
            return ParsedTransaction(
                amount=amount,
                transaction_type=TransactionType.debit,
                occurred_at=occurred_at,
                merchant=purchase.group("merchant").strip(),
                currency="COP",
                card_last_digits=purchase.group("digits")[-4:],
                raw_email_reference=envelope.message_id,
            )

        # 2. Depósito (incoming credit)
        deposit = self._DEPOSIT_RE.search(text)
        if deposit:
            return ParsedTransaction(
                amount=amount,
                transaction_type=TransactionType.credit,
                occurred_at=occurred_at,
                merchant=None,
                category=None,
                currency="COP",
                card_last_digits=deposit.group("digits")[-4:],
                raw_email_reference=envelope.message_id,
            )

        # 3. Débito genérico con canal
        debit = self._DEBIT_RE.search(text)
        if debit:
            channel_match = self._CHANNEL_RE.search(text)
            channel = channel_match.group("channel").strip() if channel_match else None
            return ParsedTransaction(
                amount=amount,
                transaction_type=TransactionType.debit,
                occurred_at=occurred_at,
                merchant=channel,
                category=None,
                currency="COP",
                card_last_digits=debit.group("digits")[-4:],
                raw_email_reference=envelope.message_id,
                # Outgoing transfers carry no recipient — only the channel. The
                # transfer matcher pairs these against incoming credits from
                # Nequi/Daviplata/Falabella. See PARSERS.md § Pareo.
                is_pairing_candidate=channel == "Portal Internet",
            )

        return None

    @staticmethod
    def _normalize_html(html_body: str) -> str:
        """Decode HTML entities, strip tags, collapse whitespace."""
        decoded = html_lib.unescape(html_body)
        no_tags = re.sub(r"<[^>]+>", " ", decoded)
        return re.sub(r"\s+", " ", no_tags).strip()

    @classmethod
    def _extract_amount(cls, text: str) -> Decimal | None:
        match = cls._AMOUNT_RE.search(text)
        if not match:
            return None
        raw = match.group(1).replace(",", "")
        try:
            return Decimal(raw)
        except Exception:
            return None

    @classmethod
    def _extract_datetime(cls, text: str) -> datetime | None:
        match = cls._DATETIME_RE.search(text)
        if not match:
            return None
        try:
            naive = datetime.strptime(
                f"{match.group(1)} {match.group(2)}",
                "%Y/%m/%d %H:%M:%S",
            )
        except ValueError:
            return None
        return naive.replace(tzinfo=COLOMBIA_TZ).astimezone(timezone.utc)
