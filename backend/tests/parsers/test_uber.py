from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from app.models.transaction import TransactionType
from app.parsers import REGISTERED_PARSERS
from app.parsers.uber import UBER_CARD_SOURCE, UberParser
from app.services.categorizer import categorize
from tests._helpers import load_eml_fixture


@pytest.fixture
def parser() -> UberParser:
    return UberParser()


def test_registered() -> None:
    assert any(isinstance(p, UberParser) for p in REGISTERED_PARSERS)


def test_trip_paid_with_the_davivienda_card(parser: UberParser) -> None:
    envelope = load_eml_fixture("uber/tarjeta_davivienda.eml")
    assert parser.can_parse(envelope)
    tx = parser.parse(envelope)

    assert tx is not None
    assert tx.amount == Decimal("4969")
    assert tx.transaction_type == TransactionType.debit
    assert tx.source == UBER_CARD_SOURCE
    assert tx.card_last_digits == "1234"
    assert tx.merchant == "Uber Moto"
    assert tx.occurred_at == envelope.received_at
    assert categorize(tx.merchant, []) == "transport"


@pytest.mark.parametrize("fixture", ["uber/efectivo.eml", "uber/cash_en.eml"])
def test_cash_trip_comes_out_of_cash(parser: UberParser, fixture: str) -> None:
    tx = parser.parse(load_eml_fixture(fixture))

    assert tx is not None
    assert tx.source == "cash"
    assert tx.card_last_digits is None
    assert tx.merchant == "Uber Moto"


def test_english_amount(parser: UberParser) -> None:
    assert parser.parse(load_eml_fixture("uber/cash_en.eml")).amount == Decimal("4918")


def test_other_card_is_left_to_its_own_email(parser: UberParser) -> None:
    envelope = load_eml_fixture("uber/tarjeta_davivienda.eml")
    other = replace(
        envelope, html_body=envelope.html_body.replace("(Davivienda)", "(RappiCard)")
    )
    assert parser.parse(other) is None


def test_non_trip_email_is_ignored(parser: UberParser) -> None:
    envelope = replace(load_eml_fixture("uber/efectivo.eml"), subject="Tu cuenta de Uber")
    assert parser.parse(envelope) is None


def test_uberya_still_counts_as_transport(parser: UberParser) -> None:
    envelope = load_eml_fixture("uber/cash_en.eml")
    renamed = replace(envelope, html_body=envelope.html_body.replace("Moto", "UberYa"))
    tx = parser.parse(renamed)

    assert tx.merchant == "Uber Ya"
    assert categorize(tx.merchant, []) == "transport"
