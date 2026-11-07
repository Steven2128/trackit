from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from app.models.transaction import TransactionType
from app.parsers import REGISTERED_PARSERS
from app.parsers.pse import PseParser, _merchant
from tests._helpers import load_eml_fixture


@pytest.fixture
def parser() -> PseParser:
    return PseParser()


def test_registered() -> None:
    assert any(isinstance(p, PseParser) for p in REGISTERED_PARSERS)


def test_can_parse_only_pse_sender(parser: PseParser) -> None:
    envelope = load_eml_fixture("pse/aprobada_factura.eml")
    assert parser.can_parse(envelope) is True
    assert parser.can_parse(replace(envelope, sender="BANCO_DAVIVIENDA@davivienda.com")) is False


def test_approved_bill_through_gateway_names_the_biller(parser: PseParser) -> None:
    envelope = load_eml_fixture("pse/aprobada_factura.eml")
    tx = parser.parse(envelope)

    assert tx is not None
    assert tx.amount == Decimal("16520.00")
    assert tx.transaction_type == TransactionType.debit
    assert tx.merchant == "Vanti S.A. ESP"
    assert tx.currency == "COP"
    assert tx.category is None
    assert tx.is_pairing_candidate is False
    # The body only has a date: the email's arrival time stands in.
    assert tx.occurred_at == envelope.received_at
    assert tx.raw_email_reference == envelope.message_id


def test_gateway_with_useless_description_keeps_the_company(parser: PseParser) -> None:
    tx = parser.parse(load_eml_fixture("pse/aprobada_agregador.eml"))

    assert tx is not None
    assert tx.amount == Decimal("105930.00")
    assert tx.merchant == "GOU PAYMENTS S.A EASPBV"


def test_rejected_returns_none(parser: PseParser) -> None:
    assert parser.parse(load_eml_fixture("pse/rechazada.eml")) is None


@pytest.mark.parametrize(
    ("company", "description", "expected"),
    [
        ("Banco de Bogota", "Valor pago por PSE a tarjeta de crédito", "Banco de Bogota"),
        ("GOU PAYMENTS S.A EASPBV", "PAGO PAGO TARJETA DE CREDITO ITAU BDB", "PAGO PAGO TARJETA DE CREDITO ITAU BDB"),
        ("101 FINTECH S.A.S.", "Vanti S.A. ESP Fra 63100161", "Vanti S.A. ESP"),
        ("GOU PAYMENTS S.A EASPBV", "PAGO 7568985", "GOU PAYMENTS S.A EASPBV"),
        ("GOU PAYMENTS S.A EASPBV", "", "GOU PAYMENTS S.A EASPBV"),
    ],
)
def test_merchant(company: str, description: str, expected: str) -> None:
    assert _merchant(company, description) == expected
