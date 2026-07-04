"""Tests for the Itaú Colombia email parser.

Fixtures live in tests/fixtures/itau_co/. Each fixture is a real, anonymized
notification email. Adding a new template = drop a new .eml in that folder
and add a test here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.models.transaction import TransactionType
from app.parsers.base import EmailEnvelope
from app.parsers.itau_co import ItauCoParser
from tests._helpers import load_eml_fixture


@pytest.fixture
def parser() -> ItauCoParser:
    return ItauCoParser()


class TestCanParse:
    def test_returns_true_for_itau_sender(self, parser: ItauCoParser) -> None:
        envelope = load_eml_fixture("itau_co/compra_debito_sector9.eml")
        assert parser.can_parse(envelope) is True

    def test_returns_false_for_other_sender(self, parser: ItauCoParser) -> None:
        envelope = EmailEnvelope(
            sender="noreply@otherbank.com",
            subject="anything",
            message_id="<x@example.com>",
            received_at=datetime.now(timezone.utc),
            html_body="<html><body>hi</body></html>",
        )
        assert parser.can_parse(envelope) is False

    def test_case_insensitive_match(self, parser: ItauCoParser) -> None:
        envelope = EmailEnvelope(
            sender="NOTIFICACIONES@CLIENTEITAU.CO",
            subject="x",
            message_id="<x>",
            received_at=datetime.now(timezone.utc),
            html_body="<html></html>",
        )
        assert parser.can_parse(envelope) is True


class TestParsePurchase:
    """Template 1: compra en <MERCHANT> desde tu (Cuenta de Ahorros|Tarjeta Credito)."""

    def test_compra_debito_sector9(self, parser: ItauCoParser) -> None:
        envelope = load_eml_fixture("itau_co/compra_debito_sector9.eml")
        tx = parser.parse(envelope)

        assert tx is not None
        assert tx.amount == Decimal("17000")
        assert tx.transaction_type == TransactionType.debit
        assert tx.merchant == "SECTOR 9 SAS"
        assert tx.currency == "COP"
        assert tx.card_last_digits == "9999"
        assert tx.category is None
        assert tx.raw_email_reference  # not empty

    def test_compra_debito_rappi(self, parser: ItauCoParser) -> None:
        envelope = load_eml_fixture("itau_co/compra_debito_rappi.eml")
        tx = parser.parse(envelope)

        assert tx is not None
        assert tx.amount == Decimal("18800")
        assert tx.transaction_type == TransactionType.debit
        assert tx.merchant == "RAPPI COLOMBIA*DL"
        assert tx.card_last_digits == "9999"

    def test_compra_credito_rappi(self, parser: ItauCoParser) -> None:
        envelope = load_eml_fixture("itau_co/compra_credito_rappi.eml")
        tx = parser.parse(envelope)

        assert tx is not None
        assert tx.amount == Decimal("26300")
        assert tx.transaction_type == TransactionType.debit
        assert tx.merchant == "RAPPI COLOMBIA*DL"
        # credit card last digits, not the savings account
        assert tx.card_last_digits == "1234"


class TestParseDeposit:
    """Template 2: depósito a tu Cuenta de Ahorros (incoming credit)."""

    def test_deposito_nomina(self, parser: ItauCoParser) -> None:
        envelope = load_eml_fixture("itau_co/deposito_nomina.eml")
        tx = parser.parse(envelope)

        assert tx is not None
        assert tx.amount == Decimal("656159")
        assert tx.transaction_type == TransactionType.credit
        assert tx.merchant is None
        assert tx.currency == "COP"
        assert tx.card_last_digits == "9999"


class TestParseGenericDebit:
    """Template 3: Débito de tu Cuenta de Ahorros + Canal."""

    def test_debito_portal_internet(self, parser: ItauCoParser) -> None:
        envelope = load_eml_fixture("itau_co/debito_portal_internet.eml")
        tx = parser.parse(envelope)

        assert tx is not None
        assert tx.amount == Decimal("46560")
        assert tx.transaction_type == TransactionType.debit
        assert tx.merchant == "Portal Internet"
        assert tx.card_last_digits == "9999"
        # No category yet — will be set to "transfer" later by the pairing job
        assert tx.category is None
        assert tx.is_pairing_candidate is True

    def test_purchase_is_not_pairing_candidate(self, parser: ItauCoParser) -> None:
        envelope = load_eml_fixture("itau_co/compra_debito_rappi.eml")
        tx = parser.parse(envelope)

        assert tx is not None
        assert tx.is_pairing_candidate is False


class TestParseDateTimezone:
    def test_occurred_at_is_utc(self, parser: ItauCoParser) -> None:
        # Source email says "2026/05/02 03:43:36" local (Colombia is UTC-5)
        # → 2026-05-02 08:43:36 UTC
        envelope = load_eml_fixture("itau_co/compra_debito_sector9.eml")
        tx = parser.parse(envelope)

        assert tx is not None
        assert tx.occurred_at.tzinfo is not None
        assert tx.occurred_at.utcoffset().total_seconds() == 0
        assert tx.occurred_at == datetime(2026, 5, 2, 8, 43, 36, tzinfo=timezone.utc)


class TestParseNegatives:
    def test_missing_html_body_returns_none(self, parser: ItauCoParser) -> None:
        envelope = EmailEnvelope(
            sender=ItauCoParser().name,  # any
            subject="Notificaciones Itau",
            message_id="<x>",
            received_at=datetime.now(timezone.utc),
            html_body=None,
        )
        assert parser.parse(envelope) is None

    def test_no_recognized_template_returns_none(self, parser: ItauCoParser) -> None:
        envelope = EmailEnvelope(
            sender="notificaciones@clienteitau.co",
            subject="Notificaciones Itau",
            message_id="<x>",
            received_at=datetime.now(timezone.utc),
            html_body=(
                "<html><body>"
                "Bienvenido a tu nuevo plan. Cambio de plan efectivo el 01/06/2026."
                "</body></html>"
            ),
        )
        assert parser.parse(envelope) is None
