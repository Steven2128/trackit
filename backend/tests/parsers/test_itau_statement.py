"""Tests for the Itaú statement PDF extractor.

The real "Multiextracto" PDF contains PII (name, email, account numbers) and
is gitignored — these tests build an equivalent PDF on the fly with
reportlab, reproducing the layout quirks that matter for extraction: a plain
overview page listing accounts in order, and per-account table pages with a
header row (plain on one page, fake-bold "doubled" on another — both forms
appear in the real document) ending in the FIN marker.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import BytesIO

from reportlab.pdfgen import canvas

from app.models.transaction import TransactionType
from app.parsers.itau_statement import extract_statement

# pdfplumber merges adjacent drawString calls into one "word" when the gap
# between them is small — these columns are spaced generously (wider than
# any rendered label/value) so each column stays a distinct word.
DAY_X, DOC_X = 40, 120
DESC_X, DESC_STEP = 220, 140
OFICINA_X, RETIROS_X, DEPOSITOS_X, SALDO_X = 550, 680, 820, 980
PAGE_SIZE = (1100, 800)


def _doubled(label: str) -> str:
    return "".join(ch * 2 for ch in label)


def _draw_header(c: canvas.Canvas, y: float, *, doubled: bool) -> None:
    t = _doubled if doubled else (lambda s: s)
    c.drawString(DAY_X, y, t("Día"))
    c.drawString(DOC_X, y, t("Documento"))
    c.drawString(DESC_X, y, t("Descripción"))
    c.drawString(OFICINA_X, y, t("Oficina"))
    c.drawString(RETIROS_X, y, t("Retiros"))
    c.drawString(DEPOSITOS_X, y, t("Depósitos"))
    c.drawString(SALDO_X, y, t("Saldo"))


def _draw_row(
    c: canvas.Canvas,
    y: float,
    day: str,
    description_words: list[str],
    *,
    retiros: str | None = None,
    depositos: str | None = None,
    saldo: str | None = None,
) -> None:
    c.drawString(DAY_X, y, day)
    c.drawString(DOC_X, y, "0")
    x = DESC_X
    for word in description_words:
        c.drawString(x, y, word)
        x += DESC_STEP
    if retiros:
        c.drawString(RETIROS_X, y, retiros)
    if depositos:
        c.drawString(DEPOSITOS_X, y, depositos)
    if saldo:
        c.drawString(SALDO_X, y, saldo)


def _build_synthetic_statement_pdf() -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=PAGE_SIZE)
    _, height = PAGE_SIZE

    # Page 1 — overview: real account order, real font (unlike the real
    # document's styled header pages, which use a broken embedded font).
    y = height - 50
    for line in (
        "Cuenta de Ahorro",
        "Número de Producto Saldo Anterior Saldo Final",
        "111-11111-1 $ 0.00 $0.00",
        "Cuenta de Ahorro",
        "Número de Producto Saldo Anterior Saldo Final",
        "222-22222-2 $ 100.00 $500.00",
    ):
        c.drawString(50, y, line)
        y -= 20
    c.showPage()

    # Page 2 — account 111-11111-1: empty, fake-bold ("doubled") header.
    y = height - 50
    _draw_header(c, y, doubled=True)
    y -= 20
    _draw_row(c, y, "30", ["Cuenta", "sin", "movimientos", "en", "el", "periodo"])
    y -= 20
    c.drawString(DAY_X, y, "***FIN EXTRACTO DE CUENTA***")
    c.showPage()

    # Page 3 — account 222-22222-2: movements, plain header.
    y = height - 50
    _draw_header(c, y, doubled=False)
    y -= 20
    _draw_row(c, y, "01", ["COMPRA", "TIENDATEST"], retiros="15,000.00", saldo="85,000.00")
    y -= 20
    _draw_row(c, y, "02", ["NC", "Transferencia"], depositos="30,000.00", saldo="115,000.00")
    y -= 20
    c.drawString(DAY_X, y, "***FIN EXTRACTO DE CUENTA***")
    c.showPage()

    c.save()
    return buf.getvalue()


class TestExtractStatement:
    def test_accounts_found_in_overview_order(self) -> None:
        sections = extract_statement(
            _build_synthetic_statement_pdf(), statement_year=2026, statement_month=6
        )

        assert [s.account for s in sections] == ["111-11111-1", "222-22222-2"]

    def test_empty_account_has_no_rows(self) -> None:
        sections = extract_statement(
            _build_synthetic_statement_pdf(), statement_year=2026, statement_month=6
        )

        empty = next(s for s in sections if s.account == "111-11111-1")
        assert empty.rows == []

    def test_movement_rows_extracted_with_correct_type_and_date(self) -> None:
        sections = extract_statement(
            _build_synthetic_statement_pdf(), statement_year=2026, statement_month=6
        )

        active = next(s for s in sections if s.account == "222-22222-2")
        assert len(active.rows) == 2

        debit, credit = active.rows
        assert debit.tx_type == TransactionType.debit
        assert debit.amount == Decimal("15000.00")
        assert debit.local_date == date(2026, 6, 1)
        assert "COMPRA" in debit.description

        assert credit.tx_type == TransactionType.credit
        assert credit.amount == Decimal("30000.00")
        assert credit.local_date == date(2026, 6, 2)

    def test_row_index_resets_per_account(self) -> None:
        sections = extract_statement(
            _build_synthetic_statement_pdf(), statement_year=2026, statement_month=6
        )

        active = next(s for s in sections if s.account == "222-22222-2")
        assert [r.index for r in active.rows] == [0, 1]
