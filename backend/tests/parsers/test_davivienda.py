from __future__ import annotations

import base64
import re
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.integrations.gmail import _decode_part_body
from app.models.transaction import TransactionType
from app.parsers.davivienda import LLAVE_MERCHANT, DaviviendaParser
from app.parsers.nequi import NequiParser
from tests._helpers import FIXTURES_DIR, load_eml_fixture


@pytest.fixture
def parser() -> DaviviendaParser:
    return DaviviendaParser()


class TestCanParse:
    def test_accepts_transactional_sender(self, parser: DaviviendaParser) -> None:
        envelope = load_eml_fixture("davivienda/compra_establecimiento.eml")
        assert parser.can_parse(envelope) is True

    def test_rejects_other_davivienda_senders(self, parser: DaviviendaParser) -> None:
        envelope = replace(
            load_eml_fixture("davivienda/compra_establecimiento.eml"),
            sender="ServicioNotificaciones@davivienda.com",
        )
        assert parser.can_parse(envelope) is False


class TestDebits:
    def test_compra_en_establecimiento(self, parser: DaviviendaParser) -> None:
        tx = parser.parse(load_eml_fixture("davivienda/compra_establecimiento.eml"))

        assert tx is not None
        assert tx.amount == Decimal("88210")
        assert tx.transaction_type == TransactionType.debit
        assert tx.merchant == "TIENDA D1 LA FLORIDA"
        assert tx.category is None
        assert tx.currency == "COP"
        assert tx.card_last_digits == "1234"
        assert tx.is_pairing_candidate is False
        # 2026/09/09 16:01:15 Bogotá → 21:01:15 UTC
        assert tx.occurred_at == datetime(2026, 9, 9, 21, 1, 15, tzinfo=timezone.utc)

    def test_descuento_en_internet_pse(self, parser: DaviviendaParser) -> None:
        tx = parser.parse(load_eml_fixture("davivienda/descuento_pse.eml"))

        assert tx is not None
        assert tx.amount == Decimal("384000")
        assert tx.transaction_type == TransactionType.debit
        assert tx.merchant == "PSE BANCO DAVIVIENDA SA"
        # 2026/09/04 20:20:19 Bogotá → next day 01:20:19 UTC
        assert tx.occurred_at == datetime(2026, 9, 5, 1, 20, 19, tzinfo=timezone.utc)

    def test_transferencia_a_llave_is_self_transfer(self, parser: DaviviendaParser) -> None:
        """Key transfers go to the user's own Nequi; Nequi's Enviaste is the spend."""
        tx = parser.parse(load_eml_fixture("davivienda/transferencia_llave.eml"))

        assert tx is not None
        assert tx.amount == Decimal("190000")
        assert tx.transaction_type == TransactionType.debit
        assert tx.merchant == LLAVE_MERCHANT
        assert tx.category == "transfer"
        assert tx.is_pairing_candidate is True
        assert tx.occurred_at == datetime(2026, 9, 6, 22, 44, 36, tzinfo=timezone.utc)


class TestCredits:
    def test_abono_pago_de_nomina(self, parser: DaviviendaParser) -> None:
        tx = parser.parse(load_eml_fixture("davivienda/abono_nomina.eml"))

        assert tx is not None
        assert tx.amount == Decimal("1136548")
        assert tx.transaction_type == TransactionType.credit
        assert tx.merchant == "Portal pyme ACME SAS"
        assert tx.category is None
        assert tx.is_pairing_candidate is False

    def test_abono_transfiya_is_income(self, parser: DaviviendaParser) -> None:
        """"Abono A Otros Bancos en Linea Transfiya" reads like an outflow but
        is money arriving (payroll) — every "Abono" class is a credit."""
        tx = parser.parse(load_eml_fixture("davivienda/abono_transfiya.eml"))

        assert tx is not None
        assert tx.amount == Decimal("1186548")
        assert tx.transaction_type == TransactionType.credit
        assert tx.merchant == "ACH EN LINEA DAVIVIENDA"


class TestSkipped:
    def test_cambio_de_clave_returns_none(self, parser: DaviviendaParser) -> None:
        assert parser.parse(load_eml_fixture("davivienda/cambio_clave.eml")) is None

    def test_no_html_body_returns_none(self, parser: DaviviendaParser) -> None:
        envelope = replace(
            load_eml_fixture("davivienda/compra_establecimiento.eml"), html_body=None
        )
        assert parser.parse(envelope) is None

    def test_mis_decoded_accents_still_parse(self, parser: DaviviendaParser) -> None:
        """Regexes must not depend on the "ó" in "Transacción" surviving decode."""
        envelope = load_eml_fixture("davivienda/compra_establecimiento.eml")
        envelope = replace(envelope, html_body=envelope.html_body.replace("ó", "�"))

        tx = parser.parse(envelope)

        assert tx is not None
        assert tx.amount == Decimal("88210")
        assert tx.merchant == "TIENDA D1 LA FLORIDA"


class TestGmailDecoding:
    """Davivienda bodies are Latin-1 while their <meta> claims UTF-8."""

    def _raw_body(self) -> str:
        raw = (FIXTURES_DIR / "davivienda/compra_establecimiento.eml").read_bytes()
        body = re.split(rb"\r?\n\r?\n", raw, maxsplit=1)[1]
        return base64.urlsafe_b64encode(body).decode("ascii")

    def test_declared_charset_is_honored(self) -> None:
        assert "Transacción" in _decode_part_body(self._raw_body(), "iso-8859-1")

    def test_undeclared_latin1_falls_back_without_mojibake(self) -> None:
        decoded = _decode_part_body(self._raw_body(), None)
        assert "Transacción" in decoded
        assert "�" not in decoded

    def test_utf8_still_decodes_as_utf8(self) -> None:
        data = base64.urlsafe_b64encode("¡Enviaste!".encode("utf-8")).decode("ascii")
        assert _decode_part_body(data, None) == "¡Enviaste!"


def test_nequi_credit_from_davivienda_is_pairing_candidate() -> None:
    """The other half of the key transfer: Nequi's Recibiste from Davivienda."""
    envelope = load_eml_fixture("nequi/recibiste_itau.eml")
    envelope = replace(
        envelope,
        html_body=envelope.html_body.replace("desde el banco Itau", "desde el banco DAVIVIENDA"),
    )

    tx = NequiParser().parse(envelope)

    assert tx is not None
    assert tx.category == "transfer"
    assert tx.is_pairing_candidate is True
