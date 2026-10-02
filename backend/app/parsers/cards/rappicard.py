"""RappiCard (Davivienda) credit card emails — noreply@rappicard.co.

Templates:

1. "RappiCard - Resumen de transacción"
   "Realizaste una compra con tu RappiCard. ... Monto $23.350 Método de pago
    *2389 No. de autorización 347907 Comercio RAPPI Fecha de la transacción
    2026-08-26 23:08:55"
   → purchase. Colombian amount ("$23.350"), local Bogotá timestamp.

2. "Comprobante de pago"
   "Recibimos el pago de tu tarjeta ... Destino de pago *4875 Fecha y hora
    04 sept 2026 15:18 Método de pago PSE Monto 384.000,0"
   → payment. The body time runs ~5h behind the bank debit that funded it,
   so occurred_at is the email's received time (sent the moment the payment
   lands). "Destino de pago" digits are not the card's digits.

3. "¡Llegó el extracto de tu RappiCard!"
   "Pago mínimo: $ 92,392.00 ... Pago total: $ 92,392.00 Fecha límite de
    pago: 20 sept 2026"
   → statement. US amount format here, Spanish abbreviated month.

Marketing from the same sender (contract signed, promos) returns None.
"""

from __future__ import annotations

import html as html_lib
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from app.parsers.base import EmailEnvelope
from app.parsers.cards.base import CardEmailParser, CardEvent, CardEventKind

COLOMBIA_TZ = timezone(timedelta(hours=-5))

_MONTHS = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}

# Colombian: dot thousands, comma decimals ("23.350", "384.000,0")
_CO_AMOUNT = r"(?P<amount>\d{1,3}(?:\.\d{3})*(?:,\d+)?)"

_PURCHASE_RE = re.compile(
    rf"Realizaste\s+una\s+compra\s+con\s+tu\s+RappiCard.*?Monto\s+\$\s*{_CO_AMOUNT}"
    r"\s+M.todo\s+de\s+pago\s+\*(?P<digits>\d{4})"
    r".*?Comercio\s+(?P<merchant>.+?)\s+Fecha\s+de\s+la\s+transacci.n\s+"
    r"(?P<ts>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})",
    re.IGNORECASE,
)

_PAYMENT_RE = re.compile(
    rf"Recibimos\s+el\s+pago\s+de\s+tu\s+tarjeta.*?Monto\s+\$?\s*{_CO_AMOUNT}",
    re.IGNORECASE,
)

_STATEMENT_RE = re.compile(
    r"Pago\s+m.nimo\s*:\s*\$\s*(?P<minimum>[\d,]+(?:\.\d+)?)"
    r".*?Fecha\s+l.mite\s+de\s+pago\s*:\s*(?P<day>\d{1,2})\s+(?P<month>[a-z]{3})[a-z]*\.?\s+(?P<year>\d{4})",
    re.IGNORECASE,
)


class RappiCardParser(CardEmailParser):
    key = "rappicard"
    label = "RappiCard"
    default_sender = "noreply@rappicard.co"

    def parse(self, envelope: EmailEnvelope) -> CardEvent | None:
        if not envelope.html_body:
            return None
        text = _normalize_html(envelope.html_body)

        purchase = _PURCHASE_RE.search(text)
        if purchase:
            amount = _co_amount(purchase.group("amount"))
            try:
                naive = datetime.strptime(purchase.group("ts"), "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return None
            if amount is None:
                return None
            return CardEvent(
                kind=CardEventKind.purchase,
                occurred_at=naive.replace(tzinfo=COLOMBIA_TZ).astimezone(timezone.utc),
                amount=amount,
                merchant=purchase.group("merchant").strip(),
                card_last_digits=purchase.group("digits"),
            )

        payment = _PAYMENT_RE.search(text)
        if payment:
            amount = _co_amount(payment.group("amount"))
            if amount is None:
                return None
            return CardEvent(
                kind=CardEventKind.payment,
                occurred_at=envelope.received_at.astimezone(timezone.utc),
                amount=amount,
            )

        statement = _STATEMENT_RE.search(text)
        if statement:
            month = _MONTHS.get(statement.group("month").lower())
            try:
                minimum = Decimal(statement.group("minimum").replace(",", ""))
                due = date(int(statement.group("year")), month, int(statement.group("day")))
            except (InvalidOperation, TypeError, ValueError):
                return None
            return CardEvent(
                kind=CardEventKind.statement,
                occurred_at=envelope.received_at.astimezone(timezone.utc),
                minimum_payment=minimum,
                payment_due_date=due,
            )

        return None


def _normalize_html(html_body: str) -> str:
    no_blocks = re.sub(r"<(style|script)\b.*?</\1>", " ", html_body, flags=re.S | re.I)
    no_tags = re.sub(r"<[^>]+>", " ", html_lib.unescape(no_blocks))
    return re.sub(r"\s+", " ", no_tags).strip()


def _co_amount(raw: str) -> Decimal | None:
    try:
        return Decimal(raw.replace(".", "").replace(",", "."))
    except InvalidOperation:
        return None
