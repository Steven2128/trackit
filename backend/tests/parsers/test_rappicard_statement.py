"""RappiCard statement PDF, from the text pdfplumber extracts (layout copied
from a real statement; amounts kept, personal data removed)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.models.transaction import TransactionType
from app.parsers.cards.rappicard_statement import parse_statement_text
from app.services.card_statement import balance_after, cutoff_instant

TEXT = """Producto emitido por Davivienda S.A.
Extracto de tarjeta de crédito
Pago mínimo
Cupo utilizado $ 757.430,83
$ 915.066,17 Fecha de pago
Periodo facturado
Pago alternativo*
20 nov 2026
Desde 09 oct 2026
$ 227.229,25
Hasta 10 nov 2026
Cupo total: $3.300.000,00 * Puedes hacer este pago desde tu aplicación de Rappi
Estado: Normal Pago total
$ 915.066,17
Saldo periodo anterior $629.703,00
+ Consumos del mes $688.072,00
- Pagos (incluye abonos y cancelaciones) $-402.708,83
Pago total $915.066,17
Pago mínimo $757.430,83
Detalle de transacciones: NOMBRE (Titular)
Tarjeta Fecha Descripción facturado Cuotas pendiente
MERCADO
Virtual 2026-09-11 $59.800,00 $19.933,33 2 de 3 $19.933,34 0,0000% 0,00%
PAGO*MERCADOLI
MERCADO
Virtual 2026-09-11 $219.703,00 $29.425,50 2 de 6 $117.702,00 0,0000% 0,00%
PAGO*MERCADOLI
MERCADO
Virtual 2026-09-29 $60.000,00 $20.000,00 2 de 3 $20.000,00 0,0000% 0,00%
PAGO*MERCADOLI
Virtual 2026-10-09 BERSHKA TESORO $285.700,00 $285.700,00 1 de 1 $0,00 0,0000% 0,00%
Fisica 2026-10-11 BOLD SA*BROSTY B $14.700,00 $14.700,00 1 de 1 $0,00 0,0000% 0,00%
- 2026-10-20 PAGOS RAPPIPAY APP $-402.708,83 N/A N/A N/A 0% 0,00%
Virtual 2026-10-21 RAPPI $25.300,00 $25.300,00 1 de 1 $0,00 0,0000% 0,00%
Fisica 2026-10-30 EXITO WOW DIVERPLAZA $10.000,00 $10.000,00 1 de 1 $0,00 0,0000% 0,00%
"""


def test_header_period_minimum_and_total() -> None:
    st = parse_statement_text(TEXT)
    assert st is not None
    assert (st.period_start, st.period_end) == (date(2026, 10, 9), date(2026, 11, 10))
    assert st.minimum_payment == Decimal("757430.83")
    assert st.total_payment == Decimal("915066.17")
    assert st.due_date == date(2026, 11, 20)
    assert st.credit_limit == Decimal("3300000.00")


def test_rows_with_wrapped_descriptions_payments_and_installments() -> None:
    st = parse_statement_text(TEXT)
    assert len(st.lines) == 8
    first = st.lines[0]
    assert (first.on, first.description, first.amount) == (
        date(2026, 9, 11), "MERCADO PAGO*MERCADOLI", Decimal("59800.00"),
    )
    assert (first.billed, first.installment, first.installments, first.pending) == (
        Decimal("19933.33"), 2, 3, Decimal("19933.34"),
    )
    payment = st.lines[5]
    assert (payment.description, payment.amount, payment.billed) == (
        "PAGOS RAPPIPAY APP", Decimal("-402708.83"), None,
    )


def test_next_statement_installments() -> None:
    # 19.933,34 (last of 3) + 117.702 / 4 + 20.000 (last of 3); 1-de-1 rows add nothing.
    st = parse_statement_text(TEXT)
    assert st.next_installments == Decimal("69358.84")


def test_purchases_are_only_those_made_in_the_period() -> None:
    st = parse_statement_text(TEXT)
    assert [(p.on, p.description) for p in st.purchases] == [
        (date(2026, 10, 9), "BERSHKA TESORO"),
        (date(2026, 10, 11), "BOLD SA*BROSTY B"),
        (date(2026, 10, 21), "RAPPI"),
        (date(2026, 10, 30), "EXITO WOW DIVERPLAZA"),
    ]


def test_text_without_a_period_is_not_a_statement() -> None:
    assert parse_statement_text("Tu contrato fue firmado") is None


def test_cutoff_is_the_start_of_the_day_after_the_period_ends() -> None:
    at = cutoff_instant(parse_statement_text(TEXT))
    assert (at.date(), at.hour, at.utcoffset().total_seconds()) == (date(2026, 11, 11), 0, -18000)


def test_balance_is_the_statement_total_plus_what_happened_after_the_cutoff() -> None:
    later = [
        (TransactionType.debit, Decimal("25000")),
        (TransactionType.credit, Decimal("757430.83")),
    ]
    assert balance_after(Decimal("915066.17"), later) == Decimal("182635.34")
    assert balance_after(Decimal("100"), [(TransactionType.credit, Decimal("500"))]) == 0
