"""Banco de Bogotá card statement, from the text pdfplumber extracts (a
synthetic copy of a real statement's layout, personal data replaced)."""

from datetime import date
from decimal import Decimal

from app.parsers.cards.bancodebogota_statement import parse_statement_text
from app.services.card_statement import balance_after
from app.models.transaction import TransactionType

TEXT = """Extracto Tarjeta Crédito
Nro. 2026111711TC0000000000
Página 1 de 1
Desde el 15 de diciembre del 2025 la tarifa del Seguro Vida Deudor de su Tarjeta de Crédito será $5.900. Más información www.bancodebogota.com
NOMBRE APELLIDO
CALLE 1 2 3
BOGOTA D.C.,BOGOTA D.C. 2133 Fecha Facturación Fecha Límite de Pago
Entrega: PE 16/11/2026 07/12/2026
Tarjeta Número 5200000000000000
Cupo Total Cupo Disponible Utilizaciones del Periodo
COMPRAS 3,600,000 1,281,962 72,300
AVANCES 1,080,000 1,080,000 0
00184678 Compras diferidas 08/10/2026 08/10/2026 50 2,258,662 28.135 43,818 49 2,147,068
55291907 PTO DE VENTA MIMO S AR 14/10/2026 16/10/2026 01 20,800 28.559 20,800 00 0
29270902 SANDWICH GOURMET DIVER 17/10/2026 19/10/2026 01 51,500 28.559 51,500 00 0
62246412 PAGO PORTAL DE PAGOS AVAL PSE 06/11/2026 06/11/2026 00 250,000 0.000 0 00 0
95161000 SEG ITAU GOLD 16/11/2026 16/11/2026 00 3,000 0.000 3,000 00 0
- - - - - - FIN MOVIMIENTOS - - - - - -
PAGO MÍNIMO PAGO TOTAL
+ Otros cargos y débitos (3) 3,000 + Otros cargos y débitos (3) 3,000 = Pago Minimo 171,000 = Pago Total 2,318,039
= Pago Minimo Alterno 101,000
"""


def test_header_values() -> None:
    st = parse_statement_text(TEXT)
    assert st is not None
    assert st.period_end == date(2026, 11, 16)
    assert st.due_date == date(2026, 12, 7)
    assert st.minimum_payment == Decimal("171000")  # not the "Alterno" one
    assert st.total_payment == Decimal("2318039")
    assert st.credit_limit == Decimal("3600000")


def test_rows() -> None:
    st = parse_statement_text(TEXT)
    deferred, mimo, sandwich, payment, fee = st.lines
    assert (deferred.installment, deferred.installments) == (1, 50)
    assert deferred.billed == Decimal("43818") and deferred.pending == Decimal("2147068")
    assert not deferred.purchase
    assert mimo.on == date(2026, 10, 14) and mimo.amount == Decimal("20800")
    assert payment.amount == Decimal("-250000")
    assert fee.amount == Decimal("3000") and fee.installments is None


def test_purchases_skip_the_deferred_balance_and_payments() -> None:
    st = parse_statement_text(TEXT)
    assert [p.description for p in st.purchases] == [
        "PTO DE VENTA MIMO S AR", "SANDWICH GOURMET DIVER", "SEG ITAU GOLD",
    ]
    assert st.period_start == date(2026, 10, 14)


def test_next_statement_bills_the_deferred_installment() -> None:
    st = parse_statement_text(TEXT)
    assert st.next_installments == Decimal("43817.71")


def test_other_banks_text_is_not_read() -> None:
    assert parse_statement_text("Extracto RappiCard Hasta 10 nov 2026") is None


def test_linked_bank_payment_after_cutoff_lowers_the_balance() -> None:
    later = [(TransactionType.debit, Decimal("558000"), "debt_payment")]
    assert balance_after(Decimal("2318039"), later) == Decimal("1760039")


def test_card_purchase_after_cutoff_raises_it() -> None:
    later = [(TransactionType.debit, Decimal("20000"), "food"),
             (TransactionType.credit, Decimal("5000"))]
    assert balance_after(Decimal("100"), later) == Decimal("15100")
