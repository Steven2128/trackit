"""Banco de Bogotá credit-card statement PDF ("Extracto Tarjeta Crédito").

The bank doesn't email it to us; the user downloads it and uploads it from
the app (POST /cards/{debt_id}/statement). Not password-protected.

Text layout (pdfplumber):

- header: "Fecha Facturación Fecha Límite de Pago" and, a line below,
  "PE 16/11/2026 07/12/2026" = cut-off day and due date (dd/mm/yyyy).
- "COMPRAS 3,600,000 1,281,962 72,300" = purchases limit, available,
  used this period.
- one row per movement:
  "55291907 PTO DE VENTA MIMO S AR 14/10/2026 16/10/2026 01 20,800 28.559 20,800 00 0"
  = voucher, description, transaction date, posting date, term (cuotas),
  original amount, annual rate, installment billed this month, installments
  left, capital still to bill. Payments have term 00 and a 0 installment
  ("PAGO PORTAL DE PAGOS AVAL PSE ..."); fees have term 00 and bill their
  whole amount ("SEG ITAU GOLD").
- "= Pago Minimo 171,000" and "= Pago Total 2,318,039" (whole balance, the
  deferred capital included). "= Pago Minimo Alterno" is a different thing.

Amounts use commas for thousands and no cents.

"Compras diferidas" is the old balance turned into installments, not a
purchase: it only bills its installment.
"""

from __future__ import annotations

import calendar
import re
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

from app.parsers.cards.rappicard_statement import CardStatement, StatementLine

_AMOUNT = r"\d{1,3}(?:,\d{3})*"
_DMY = r"(\d{2})/(\d{2})/(\d{4})"

_MARKER_RE = re.compile(r"Extracto\s+Tarjeta\s+Cr.dito", re.IGNORECASE)
_DATES_RE = re.compile(rf"Fecha\s+Facturaci.n.*?{_DMY}\s+{_DMY}", re.IGNORECASE | re.DOTALL)
_MINIMUM_RE = re.compile(rf"=\s*Pago\s+M.nimo\s+({_AMOUNT})(?!\S)", re.IGNORECASE)
_TOTAL_RE = re.compile(rf"=\s*Pago\s+Total\s+({_AMOUNT})", re.IGNORECASE)
_LIMIT_RE = re.compile(rf"^COMPRAS\s+({_AMOUNT})\s+{_AMOUNT}\s+{_AMOUNT}\s*$", re.MULTILINE)
_ROW_RE = re.compile(
    rf"^(?P<voucher>\d{{5,}})\s+(?P<desc>.+?)\s+"
    rf"(?P<on>\d{{2}}/\d{{2}}/\d{{4}})\s+(?P<posted>\d{{2}}/\d{{2}}/\d{{4}})\s+"
    rf"(?P<term>\d{{1,3}})\s+(?P<amount>{_AMOUNT})\s+(?P<rate>\d+\.\d+)\s+"
    rf"(?P<billed>{_AMOUNT})\s+(?P<left>\d{{1,3}})\s+(?P<pending>{_AMOUNT})\s*$"
)
_PAYMENT_RE = re.compile(r"^(PAGO|ABONO)\b", re.IGNORECASE)
_DEFERRED_RE = re.compile(r"^COMPRAS?\s+DIFERIDAS?\b", re.IGNORECASE)


def is_statement(text: str) -> bool:
    return bool(_MARKER_RE.search(text)) and "bancodebogota" in text.lower()


def extract_statement(pdf_bytes: bytes, password: str | None = None) -> CardStatement | None:
    """Read the PDF. Raises if it can't be opened."""
    import pdfplumber

    with pdfplumber.open(BytesIO(pdf_bytes), password=password or None) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    return parse_statement_text(text)


def parse_statement_text(text: str) -> CardStatement | None:
    """None when the text isn't a Banco de Bogotá card statement."""
    if not is_statement(text):
        return None
    dates = _DATES_RE.search(text)
    if dates is None:
        return None
    period_end = _dmy(*dates.group(1, 2, 3))
    statement = CardStatement(
        period_start=None,
        period_end=period_end,
        minimum_payment=_amount(_MINIMUM_RE.search(text)),
        total_payment=_amount(_TOTAL_RE.search(text)),
        due_date=_dmy(*dates.group(4, 5, 6)),
        credit_limit=_amount(_LIMIT_RE.search(text)),
    )
    for raw in text.splitlines():
        row = _ROW_RE.match(raw.strip())
        if row is None:
            continue
        description = " ".join(row.group("desc").split())
        on = _dmy(*row.group("on").split("/"))
        amount = _num(row.group("amount"))
        term = int(row.group("term"))
        billed = _num(row.group("billed"))
        left = int(row.group("left"))
        pending = _num(row.group("pending"))
        if term == 0 and billed == 0 and _PAYMENT_RE.match(description):
            line = StatementLine(
                index=len(statement.lines), on=on, description=description, amount=-amount
            )
        elif term == 0:
            # A fee or charge billed whole this month.
            line = StatementLine(
                index=len(statement.lines), on=on, description=description,
                amount=amount, billed=billed,
            )
        else:
            installment = max(term - left, 1)
            line = StatementLine(
                index=len(statement.lines),
                on=on,
                description=description,
                amount=amount,
                billed=billed,
                installment=installment,
                installments=term,
                pending=pending,
                # First time it bills = bought this period; later months only
                # carry its installment. The deferred old balance never is.
                purchase=installment == 1 and not _DEFERRED_RE.match(description),
            )
        statement.lines.append(line)
    statement.period_start = _period_start(statement)
    return statement


def _period_start(statement: CardStatement) -> date:
    """The PDF doesn't print the period. Its first purchase starts it (older
    lines are installments of something bought before); with no purchase,
    the day after the cut-off a month earlier."""
    bought = [line.on for line in statement.lines if line.amount > 0 and line.purchase]
    if bought:
        return min(bought)
    end = statement.period_end
    year, month = (end.year - 1, 12) if end.month == 1 else (end.year, end.month - 1)
    day = min(end.day, calendar.monthrange(year, month)[1])
    return date(year, month, day) + timedelta(days=1)


def _num(raw: str) -> Decimal:
    return Decimal(raw.replace(",", ""))


def _amount(match: re.Match | None) -> Decimal | None:
    return _num(match.group(1)) if match else None


def _dmy(day: str, month: str, year: str) -> date:
    return date(int(year), int(month), int(day))
