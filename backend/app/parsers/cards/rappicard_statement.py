"""RappiCard monthly statement PDF — attached to the "¡Llegó el extracto de
tu RappiCard!" email (password-protected: ``RAPPICARD_STATEMENT_PDF_PASSWORD``).

The email body only has the minimum and the due date; the PDF has the rest:

- page 1: "Periodo facturado Desde 09 oct 2026 / Hasta 10 nov 2026" (the
  "Hasta" day is the cut-off), "Pago mínimo $757.430,83",
  "Pago total $915.066,17" (the whole balance, unbilled installments
  included), "Cupo total: $3.300.000,00". The boxes interleave when
  extracted as text, so only labels that sit on one line with their value
  are read; the due date ("Fecha de pago") is the one date alone on a line.
- page 2+: one line per movement —
  "Fisica 2026-10-27 TIENDA D1 LA FLORIDA $74.650,00 $74.650,00 1 de 1 $0,00 0,0000% 0,00%"
  = card, date, description, purchase amount, capital billed this period,
  installment "n de N", capital still to bill. Payments are negative with
  "N/A N/A N/A". A long description wraps around its row: the row line has
  no description and the two halves sit on the lines before and after.

Amounts are Colombian ("1.234,56"); months are Spanish abbreviations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from io import BytesIO

_MONTHS = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}
_AMOUNT = r"-?\d{1,3}(?:\.\d{3})*,\d{2}"
_DATE = r"(\d{1,2})\s+([a-z]{3})[a-z]*\.?\s+(\d{4})"

_FROM_RE = re.compile(rf"Desde\s+{_DATE}", re.IGNORECASE)
_TO_RE = re.compile(rf"Hasta\s+{_DATE}", re.IGNORECASE)
_MINIMUM_RE = re.compile(rf"Pago\s+m.nimo[ \t]+\$[ \t]*({_AMOUNT})", re.IGNORECASE)
_LIMIT_RE = re.compile(rf"Cupo\s+total:?[ \t]*\$[ \t]*({_AMOUNT})", re.IGNORECASE)
_DUE_RE = re.compile(rf"^[ \t]*{_DATE}[ \t]*$", re.IGNORECASE | re.MULTILINE)
_TOTAL_RE = re.compile(rf"Pago\s+total[ \t]+\$[ \t]*({_AMOUNT})", re.IGNORECASE)
_ROW_RE = re.compile(
    rf"^(?P<card>Virtual|F.sica|-)\s+(?P<date>\d{{4}}-\d{{2}}-\d{{2}})\s+(?P<desc>.*?)\s*"
    rf"\$(?P<amount>{_AMOUNT})\s+"
    rf"(?:\$(?P<billed>{_AMOUNT})\s+(?P<n>\d+)\s+de\s+(?P<of>\d+)\s+\$(?P<pending>{_AMOUNT})"
    r"|N/A\s+N/A\s+N/A)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class StatementLine:
    index: int
    on: date
    description: str
    amount: Decimal  # negative = payment
    billed: Decimal | None = None  # capital billed in this statement
    installment: int | None = None
    installments: int | None = None
    pending: Decimal | None = None  # capital left for later statements

    @property
    def next_installment(self) -> Decimal:
        """What this purchase will bill in the next statement."""
        if not self.pending or not self.installments or not self.installment:
            return Decimal("0")
        left = self.installments - self.installment
        if left <= 0:
            return Decimal("0")
        return (self.pending / left).quantize(Decimal("0.01"))


@dataclass
class CardStatement:
    period_start: date | None
    period_end: date  # the cut-off day
    minimum_payment: Decimal | None
    total_payment: Decimal | None
    due_date: date | None = None
    credit_limit: Decimal | None = None
    lines: list[StatementLine] = field(default_factory=list)

    @property
    def next_installments(self) -> Decimal:
        return sum((line.next_installment for line in self.lines), Decimal("0"))

    @property
    def purchases(self) -> list[StatementLine]:
        """Bought in this period (older purchases only show their installment)."""
        return [
            line
            for line in self.lines
            if line.amount > 0
            and (self.period_start is None or line.on >= self.period_start)
            and line.on <= self.period_end
        ]


def extract_statement(pdf_bytes: bytes, password: str | None = None) -> CardStatement | None:
    """Read the PDF. Raises if it can't be opened (wrong or missing password)."""
    import pdfplumber

    with pdfplumber.open(BytesIO(pdf_bytes), password=password or None) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    return parse_statement_text(text)


def parse_statement_text(text: str) -> CardStatement | None:
    """None when the text isn't a statement (no billing period)."""
    period_end = _date(_TO_RE.search(text))
    if period_end is None:
        return None
    statement = CardStatement(
        period_start=_date(_FROM_RE.search(text)),
        period_end=period_end,
        minimum_payment=_amount(_MINIMUM_RE.search(text)),
        total_payment=_amount(_TOTAL_RE.search(text)),
        due_date=_date(_DUE_RE.search(text)),
        credit_limit=_amount(_LIMIT_RE.search(text)),
    )
    lines = [line.strip() for line in text.splitlines()]
    for i, line in enumerate(lines):
        row = _ROW_RE.match(line)
        if row is None:
            continue
        description = row.group("desc").strip()
        if not description:
            # Wrapped: the halves are the lines right before and after.
            around = [lines[j] for j in (i - 1, i + 1) if 0 <= j < len(lines)]
            description = " ".join(part for part in around if part and not _ROW_RE.match(part))
        try:
            on = date.fromisoformat(row.group("date"))
        except ValueError:
            continue
        statement.lines.append(
            StatementLine(
                index=len(statement.lines),
                on=on,
                description=description,
                amount=_co(row.group("amount")),
                billed=_co(row.group("billed")) if row.group("billed") else None,
                installment=int(row.group("n")) if row.group("n") else None,
                installments=int(row.group("of")) if row.group("of") else None,
                pending=_co(row.group("pending")) if row.group("pending") else None,
            )
        )
    return statement


def _co(raw: str) -> Decimal:
    return Decimal(raw.replace(".", "").replace(",", "."))


def _amount(match: re.Match | None) -> Decimal | None:
    return _co(match.group(1)) if match else None


def _date(match: re.Match | None) -> date | None:
    if match is None:
        return None
    month = _MONTHS.get(match.group(2).lower())
    if month is None:
        return None
    try:
        return date(int(match.group(3)), month, int(match.group(1)))
    except ValueError:
        return None
