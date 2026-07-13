"""Extract movement rows from an Itaú Colombia monthly-statement PDF
("Multiextracto de Ahorros").

Feeds `app/services/statement_reconciler.py` from the automatic email→PDF
flow (`app/services/statement_sync.py`), the same way
`app/scripts/reconcile_statement.py` feeds it from a manually-exported CSV.

Layout notes (verified against a real "Multiextracto" fixture, one savings
account with movements + two empty ones):

- The PDF has NO machine-readable account number or period on the pages
  that carry the pretty "Información de tu cuenta" / "Información del
  corte" boxes — those pages embed their text with a broken ToUnicode CMap
  (`pdfplumber`/`pdfminer` sees only `(cid:NN)` glyphs). The overview page
  (page 1) uses a normal font and lists every account + balances in the same
  order the table sections appear later, so account numbers are sourced from
  there instead. The period (month/year) isn't recoverable from the PDF at
  all — the caller must supply it (from the statement email's received date).
- Each account section is one or more consecutive "table pages" (pages
  whose header row includes "Retiros"/"Depósitos"), ending in a page whose
  text contains `***FIN EXTRACTO DE CUENTA***`.
- Table header labels are sometimes doubled per character
  ("RReettiirrooss") — a fake-bold rendering trick used on the first page of
  each section. Both the plain and doubled forms are matched.
- Row columns: Día (day-of-month only) | Número de Documento | Descripción |
  Oficina Transacción | Retiros | Depósitos | Saldo. Exactly one of
  Retiros/Depósitos is populated per row; classification is by x-position
  relative to the midpoint between the two header columns, since amounts
  don't carry a sign.
- "Cuenta sin movimientos en el periodo" rows and "Pasan . . ." page-break
  subtotal rows are skipped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from io import BytesIO

import pdfplumber

from app.models.transaction import TransactionType
from app.services.statement_reconciler import StatementRow

_DAY_RE = re.compile(r"^\d{1,2}$")
_AMOUNT_RE = re.compile(r"^[\d,]+\.\d{2}$")
_ACCOUNT_RE = re.compile(r"\b(\d{3}-\d{5}-\d)\b")
_FIN_MARKER = "***FIN EXTRACTO DE CUENTA***"
_EMPTY_MARKER = "Cuenta sin movimientos en el periodo"

# Fallback column boundaries (points from page left edge), tuned to the
# observed template. Used only if a page's header row can't be located.
_DEFAULT_OFICINA_X0 = 315.0
_DEFAULT_BOUNDARY_X = 450.0


@dataclass
class StatementSection:
    account: str
    rows: list[StatementRow]


def _doubled(label: str) -> str:
    """Reproduce the fake-bold rendering: each character repeated twice."""
    return "".join(ch * 2 for ch in label)


def _header_word(words: list[dict], label: str) -> dict | None:
    plain, bold = label, _doubled(label)
    for w in words:
        if w["text"] in (plain, bold):
            return w
    return None


def _ordered_accounts(overview_text: str) -> list[str]:
    return _ACCOUNT_RE.findall(overview_text)


def _is_table_page(words: list[dict]) -> bool:
    has_retiros = _header_word(words, "Retiros") is not None
    has_depositos = _header_word(words, "Depósitos") is not None
    return has_retiros and has_depositos


def _group_lines(words: list[dict]) -> list[list[dict]]:
    lines: dict[float, list[dict]] = {}
    for w in words:
        key = round(w["top"])
        lines.setdefault(key, []).append(w)
    return [sorted(line, key=lambda w: w["x0"]) for _, line in sorted(lines.items())]


def _parse_amount(text: str) -> Decimal:
    return Decimal(text.replace(",", ""))


def extract_statement(
    pdf_bytes: bytes,
    *,
    statement_year: int,
    statement_month: int,
    password: str | None = None,
) -> list[StatementSection]:
    """Parse a Multiextracto PDF into per-account `StatementRow` lists.

    ``statement_year``/``statement_month`` set the date for every row (the
    PDF only carries the day-of-month per row) — pass the period the
    statement covers, derived from the email that carried this attachment.
    """
    sections: list[StatementSection] = []
    current_rows: list[StatementRow] = []
    row_index = 0
    oficina_x0 = _DEFAULT_OFICINA_X0
    boundary_x = _DEFAULT_BOUNDARY_X

    with pdfplumber.open(BytesIO(pdf_bytes), password=password or "") as pdf:
        accounts = _ordered_accounts(pdf.pages[0].extract_text() or "")

        for page in pdf.pages:
            words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
            if not _is_table_page(words):
                continue

            retiros = _header_word(words, "Retiros")
            depositos = _header_word(words, "Depósitos")
            oficina = _header_word(words, "Oficina")
            if retiros is not None and depositos is not None:
                boundary_x = (
                    (retiros["x0"] + retiros["x1"]) / 2 + (depositos["x0"] + depositos["x1"]) / 2
                ) / 2
            if oficina is not None:
                oficina_x0 = oficina["x0"]

            for line in _group_lines(words):
                day_token = line[0]["text"]
                if not _DAY_RE.match(day_token):
                    continue  # header row, "Pasan ...", branding lines, etc.

                line_text = " ".join(w["text"] for w in line)
                if _EMPTY_MARKER in line_text:
                    continue

                amounts = [w for w in line if _AMOUNT_RE.match(w["text"])]
                if len(amounts) != 2:
                    continue  # expect exactly one movement amount + saldo
                amount_word, _saldo_word = amounts

                description = " ".join(
                    w["text"]
                    for w in line[2:]  # skip day + "Número de Documento" token
                    if w["x1"] <= oficina_x0 and not _AMOUNT_RE.match(w["text"])
                )
                if not description:
                    continue

                day = int(day_token)
                try:
                    local_date = date(statement_year, statement_month, day)
                except ValueError:
                    continue

                tx_type = (
                    TransactionType.debit
                    if amount_word["x0"] < boundary_x
                    else TransactionType.credit
                )

                current_rows.append(
                    StatementRow(
                        index=row_index,
                        local_date=local_date,
                        description=description,
                        amount=_parse_amount(amount_word["text"]),
                        tx_type=tx_type,
                    )
                )
                row_index += 1

            if _FIN_MARKER in (page.extract_text() or ""):
                account = (
                    accounts[len(sections)]
                    if len(sections) < len(accounts)
                    else f"unknown-account-{len(sections)}"
                )
                sections.append(StatementSection(account=account, rows=current_rows))
                current_rows = []
                row_index = 0

    return sections
