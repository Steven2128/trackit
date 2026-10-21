"""Parser for Banco Davivienda (Colombia) account movement emails.

Sender: BANCO_DAVIVIENDA@davivienda.com
Subject (always the same): "DAVIVIENDA" — the body decides.

Every movement uses one template:

   "Le informamos que se ha registrado el siguiente movimiento de su Cta de
    Ahorros terminada (o) en ****<DIGITS>:
    Fecha: 2026/09/04 Hora: 16:37:31
    Valor Transacción: $94,300
    Clase de Movimiento: Compra en Establecimiento,
    Lugar de Transacción: COMCEL PAGO DE FACTURA"

The direction comes from "Clase de Movimiento":

- "Abono ..." (Pago de Nomina, de Proveedores, A Otros Bancos en Linea
  Transfiya) → credit. Davivienda is the user's payroll account, so these are
  real income. merchant = Lugar de Transacción. "Abono Transferencia ACH"
  (the bonus and the 20th payroll) comes with Lugar = "0000…": with no
  place, the merchant is the class itself ("Transferencia ACH").
- "Descuento Transferencia a una llave" → debit, category = "transfer".
  The user only sends to a Bre-B key to move money into their own Nequi and
  pay from there; the real spend is Nequi's "Enviaste" email. Flagged as a
  pairing candidate so the matcher links it to Nequi's "Recibiste".
- "Retiro ..." (ATM) → debit, category = "cash_withdrawal" — the money moves
  to the user's cash account, it isn't spent yet. No real sample yet; the
  class name is assumed from Davivienda's naming.
- Anything else with an amount (Compra en Establecimiento, Descuento en
  Internet / PSE, ...) → debit, merchant = Lugar de Transacción.

Notices without "Valor Transacción" (e.g. "Cambio de Clave") return None.

Format gotchas:
- Amounts use US formatting like Itaú ("$1,186,548").
- Bodies were Latin-1 until September 2026 and are UTF-8 since October;
  regexes use "." for accented letters so either decodes.
- Davivienda itself breaks non-ASCII letters in some places: the email
  carries one U+FFFD per lost letter ("PSE NEQUI S.A. COMPA<FFFD><FFFD>A D"
  for COMPAÑÍA), so they can't be recovered from the bytes. Known words are
  repaired; a single U+FFFD between letters becomes "Ñ" (upper-case company
  names drop accents but keep the Ñ); any other U+FFFD is dropped.
- Classes are padded with runs of spaces ("Compra       en Establecimiento,")
  and sometimes end in a comma.
"""

from __future__ import annotations

import html as html_lib
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models.transaction import TransactionType
from app.parsers.base import EmailEnvelope, EmailParser, ParsedTransaction

DAVIVIENDA_SENDER = "banco_davivienda@davivienda.com"

# Merchant for outgoing Bre-B key transfers — the transfer matcher pairs it
# against inbound Nequi credits.
LLAVE_MERCHANT = "Transferencia llave Davivienda"

# Colombia is UTC-5 year-round (no DST).
COLOMBIA_TZ = timezone(timedelta(hours=-5))

_ACCOUNT_RE = re.compile(r"terminada\s*\(o\)\s*en\s*\*+(?P<digits>\d{3,})", re.IGNORECASE)
_DATETIME_RE = re.compile(
    r"Fecha\s*:\s*(?P<date>\d{4}/\d{2}/\d{2})\s+Hora\s*:\s*(?P<time>\d{2}:\d{2}:\d{2})",
    re.IGNORECASE,
)
_AMOUNT_RE = re.compile(r"Valor\s+Transacci.n\s*:\s*\$\s*(?P<amount>[\d,]+(?:\.\d+)?)", re.IGNORECASE)
_BROKEN = "�"  # what Davivienda leaves where a non-ASCII letter was
_BROKEN_WORDS = ((re.compile(rf"COMPA{_BROKEN}{{1,2}}A", re.IGNORECASE), "COMPAÑÍA"),)
_BROKEN_ENYE_RE = re.compile(rf"(?<=[A-Za-z]){_BROKEN}(?=[A-Za-z])")
_NO_PLACE_RE = re.compile(r"^[\d\s.-]*$")
_CLASS_RE = re.compile(
    r"Clase\s+de\s+Movimiento\s*:\s*(?P<cls>.+?),?\s+Lugar\s+de\s+Transacci.n\s*:"
    r"\s*(?P<place>.+?)\s+Atentamente",
    re.IGNORECASE,
)


class DaviviendaParser(EmailParser):
    name = "davivienda"
    sender_filter = DAVIVIENDA_SENDER

    def can_parse(self, envelope: EmailEnvelope) -> bool:
        return DAVIVIENDA_SENDER in envelope.sender.lower()

    def parse(self, envelope: EmailEnvelope) -> ParsedTransaction | None:
        if not envelope.html_body:
            return None

        text = self._normalize_html(envelope.html_body)

        amount = self._extract_amount(text)
        occurred_at = self._extract_datetime(text)
        movement = _CLASS_RE.search(text)
        if amount is None or occurred_at is None or movement is None:
            return None

        movement_class = re.sub(r"\s+", " ", movement.group("cls")).strip(" ,.")
        place = self._clean_place(movement.group("place"), movement_class)
        account = _ACCOUNT_RE.search(text)
        digits = account.group("digits")[-4:] if account else None
        lowered = movement_class.lower()

        common = dict(
            amount=amount,
            occurred_at=occurred_at,
            currency="COP",
            card_last_digits=digits,
            raw_email_reference=envelope.message_id,
        )

        if lowered.startswith("abono"):
            return ParsedTransaction(
                transaction_type=TransactionType.credit,
                merchant=place,
                **common,
            )

        if "llave" in lowered:
            return ParsedTransaction(
                transaction_type=TransactionType.debit,
                merchant=LLAVE_MERCHANT,
                # Self-transfer to the user's Nequi, never spending on its own.
                category="transfer",
                is_pairing_candidate=True,
                **common,
            )

        return ParsedTransaction(
            transaction_type=TransactionType.debit,
            merchant=place,
            category="cash_withdrawal" if lowered.startswith("retiro") else None,
            **common,
        )

    @staticmethod
    def _clean_place(place: str, movement_class: str) -> str:
        """Repair the letters Davivienda breaks (U+FFFD), and fall back to the
        movement class when the place is only zeros (ACH credits)."""
        for pattern, word in _BROKEN_WORDS:
            place = pattern.sub(word, place)
        place = _BROKEN_ENYE_RE.sub("Ñ", place).replace(_BROKEN, "").strip()
        if _NO_PLACE_RE.match(place):
            # "Abono Transferencia ACH" → "Transferencia ACH"
            words = movement_class.split(" ", 1)
            return words[1] if len(words) > 1 else movement_class
        return place

    @staticmethod
    def _normalize_html(html_body: str) -> str:
        """Decode HTML entities, strip tags, collapse whitespace."""
        decoded = html_lib.unescape(html_body)
        no_tags = re.sub(r"<[^>]+>", " ", decoded)
        return re.sub(r"\s+", " ", no_tags).strip()

    @staticmethod
    def _extract_amount(text: str) -> Decimal | None:
        match = _AMOUNT_RE.search(text)
        if not match:
            return None
        try:
            return Decimal(match.group("amount").replace(",", ""))
        except Exception:
            return None

    @staticmethod
    def _extract_datetime(text: str) -> datetime | None:
        match = _DATETIME_RE.search(text)
        if not match:
            return None
        try:
            naive = datetime.strptime(
                f"{match.group('date')} {match.group('time')}", "%Y/%m/%d %H:%M:%S"
            )
        except ValueError:
            return None
        return naive.replace(tzinfo=COLOMBIA_TZ).astimezone(timezone.utc)
