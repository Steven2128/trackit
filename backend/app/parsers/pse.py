"""Parser for PSE (ACH Colombia) payment receipts.

Sender: serviciopse@achcolombia.com.co
Subject: "PSE - Transacción Aprobada ✅ CUS 810644537" (or "Rechazada ❌").

Body:

   "Los siguientes son los datos de tu transacción:
    Valor: $ 16.520,00
    Empresa: 101 FINTECH S.A.S.
    Descripción: Vanti S.A. ESP Fra 63100161
    Fecha de la transacción: 07/11/2026
    CUS: 810604462"

Why parse it at all: the paying bank sends its own debit email (Davivienda's
"Descuento en Internet", Nequi's "Pago exitoso"), but sometimes that email
never arrives or arrives hours late. The PSE receipt is a backup copy of the
same payment. Every approved receipt is stored as a debit with
``source="pse"``, and ``transfer_matcher.reconcile_receipts`` merges it into the
bank debit when that one shows up, so the payment is counted once.

- Only approved receipts become a transaction; rejected or pending → None.
- The receipt doesn't name the paying bank or carry a time, only a date:
  ``occurred_at`` is the email's arrival time (it lands seconds after the
  bank debit).
- Amounts use Colombian formatting ("$ 105.930,00").
- "Empresa" is often a payment gateway (GOU PAYMENTS, 101 FINTECH) and the
  real biller is in "Descripción" ("Vanti S.A. ESP Fra 63100161"). For
  gateways the merchant is the description without invoice numbers, unless
  that leaves nothing useful ("PAGO 7568985").
"""

from __future__ import annotations

import html as html_lib
import re
from decimal import Decimal

from app.models.transaction import TransactionType
from app.parsers.base import EmailEnvelope, EmailParser, ParsedTransaction

PSE_SENDER = "serviciopse@achcolombia.com.co"

# Gateways that collect for someone else; the biller is in the description.
_GATEWAYS = ("GOU PAYMENTS", "101 FINTECH", "PAYMENTSWAY", "PLACETOPAY", "EPAYCO", "PAYU")

_APPROVED_RE = re.compile(r"Transacci.n\s+Aprobada", re.IGNORECASE)
_AMOUNT_RE = re.compile(r"Valor\s*:\s*\$\s*(?P<amount>[\d.]+(?:,\d+)?)", re.IGNORECASE)
_COMPANY_RE = re.compile(r"Empresa\s*:\s*(?P<v>.+?)\s+Descripci.n\s*:", re.IGNORECASE)
_DESCRIPTION_RE = re.compile(
    r"Descripci.n\s*:\s*(?P<v>.*?)\s+Fecha\s+de\s+la\s+transacci.n", re.IGNORECASE
)
# Invoice / reference noise in descriptions: "Fra 63100161", "7568985",
# "powered by Paymentsway".
_DESCRIPTION_NOISE = (
    re.compile(r"\bpowered\s+by\b.*$", re.IGNORECASE),
    re.compile(r"\b(?:Fra|Factura|Ref|Referencia)\.?\s*\d+", re.IGNORECASE),
    re.compile(r"\b\d{4,}\b"),
)
_USELESS_DESCRIPTION_RE = re.compile(r"^(?:pago\s*)*$", re.IGNORECASE)


class PseParser(EmailParser):
    name = "pse"
    sender_filter = PSE_SENDER

    def can_parse(self, envelope: EmailEnvelope) -> bool:
        return PSE_SENDER in envelope.sender.lower()

    def parse(self, envelope: EmailEnvelope) -> ParsedTransaction | None:
        body = envelope.html_body or envelope.text_body
        if not body or not _APPROVED_RE.search(envelope.subject):
            return None

        text = _normalize(body)
        amount = _extract_amount(text)
        company = _search(_COMPANY_RE, text)
        if amount is None or company is None:
            return None

        return ParsedTransaction(
            amount=amount,
            transaction_type=TransactionType.debit,
            occurred_at=envelope.received_at,
            merchant=_merchant(company, _search(_DESCRIPTION_RE, text) or ""),
            currency="COP",
            raw_email_reference=envelope.message_id,
        )


def _merchant(company: str, description: str) -> str:
    if not any(g in company.upper() for g in _GATEWAYS):
        return company
    cleaned = description
    for pattern in _DESCRIPTION_NOISE:
        cleaned = pattern.sub(" ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .-")
    if not cleaned or _USELESS_DESCRIPTION_RE.match(cleaned):
        return company
    return cleaned


def _normalize(body: str) -> str:
    no_style = re.sub(r"<(style|script)\b.*?</\1>", " ", body, flags=re.IGNORECASE | re.DOTALL)
    no_tags = re.sub(r"<[^>]+>", " ", no_style)
    return re.sub(r"\s+", " ", html_lib.unescape(no_tags)).strip()


def _search(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    if not match:
        return None
    value = match.group("v").strip()
    return value or None


def _extract_amount(text: str) -> Decimal | None:
    match = _AMOUNT_RE.search(text)
    if not match:
        return None
    try:
        return Decimal(match.group("amount").replace(".", "").replace(",", "."))
    except Exception:
        return None
