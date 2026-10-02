from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.models.transaction import TransactionType
from app.parsers.base import EmailEnvelope
from app.parsers.nequi import NequiParser
from tests._helpers import load_eml_fixture


@pytest.fixture
def parser() -> NequiParser:
    return NequiParser()


class TestCanParse:
    def test_accepts_transactional_sender(self, parser: NequiParser) -> None:
        envelope = load_eml_fixture("nequi/recibiste_itau.eml")
        assert parser.can_parse(envelope) is True

    def test_accepts_payments_sender(self, parser: NequiParser) -> None:
        envelope = load_eml_fixture("nequi/pago_exitoso.eml")
        assert parser.can_parse(envelope) is True

    def test_rejects_marketing_sender(self, parser: NequiParser) -> None:
        envelope = EmailEnvelope(
            sender="somos@notificaciones.nequi.com.co",
            subject="Conoce los términos y condiciones",
            message_id="<x@nequi.com.co>",
            received_at=datetime.now(timezone.utc),
            html_body="<html><body>marketing</body></html>",
        )
        assert parser.can_parse(envelope) is False


class TestRecibiste:
    """Incoming Bre-B credit — the transfer matcher's credit side."""

    def test_recibiste_from_itau(self, parser: NequiParser) -> None:
        envelope = load_eml_fixture("nequi/recibiste_itau.eml")
        tx = parser.parse(envelope)

        assert tx is not None
        assert tx.amount == Decimal("15000")
        assert tx.transaction_type == TransactionType.credit
        assert tx.merchant == "Nequi"
        assert tx.currency == "COP"
        # Parking destination — inbound Nequi money is never received income.
        assert tx.category == "transfer"
        # Sourced from the user's own Itaú — pairing candidate.
        assert tx.is_pairing_candidate is True
        # "3 de julio de 2026 a las 3:07 p.m" Bogotá → 20:07 UTC
        assert tx.occurred_at == datetime(2026, 7, 3, 20, 7, tzinfo=timezone.utc)

    def test_recibiste_singular_hour_and_millions(self, parser: NequiParser) -> None:
        """'a la 1:55 p.m' (singular) + dot-thousands in the millions."""
        envelope = load_eml_fixture("nequi/recibiste_itau_hora_singular.eml")
        tx = parser.parse(envelope)

        assert tx is not None
        assert tx.amount == Decimal("1647000")
        assert tx.is_pairing_candidate is True
        assert tx.occurred_at == datetime(2026, 7, 1, 18, 55, tzinfo=timezone.utc)

    def test_recibiste_from_other_bank_is_not_candidate(self, parser: NequiParser) -> None:
        """Money from someone else's bank isn't pairable, but it still lands
        in the Nequi parking account — tagged transfer, excluded from income."""
        envelope = load_eml_fixture("nequi/recibiste_otro_banco.eml")
        tx = parser.parse(envelope)

        assert tx is not None
        assert tx.amount == Decimal("80000")
        assert tx.transaction_type == TransactionType.credit
        assert tx.category == "transfer"
        assert tx.is_pairing_candidate is False
        # "10:20 a.m" Bogotá → 15:20 UTC
        assert tx.occurred_at == datetime(2026, 6, 29, 15, 20, tzinfo=timezone.utc)


class TestEnviaste:
    """Outgoing Bre-B send — real outflow from the Nequi balance."""

    def test_enviaste_to_person(self, parser: NequiParser) -> None:
        envelope = load_eml_fixture("nequi/enviaste_breb.eml")
        tx = parser.parse(envelope)

        assert tx is not None
        assert tx.amount == Decimal("23000")
        assert tx.transaction_type == TransactionType.debit
        assert tx.merchant == "MARIA LOPEZ"
        assert tx.is_pairing_candidate is False
        # "30 de junio de 2026 a las 8:45 p.m" Bogotá → 1 jul 01:45 UTC
        assert tx.occurred_at == datetime(2026, 7, 1, 1, 45, tzinfo=timezone.utc)


class TestPagos:
    """PSE and bill payments from the Nequi balance (somos@nequi.com.co)."""

    def test_pago_exitoso(self, parser: NequiParser) -> None:
        tx = parser.parse(load_eml_fixture("nequi/pago_exitoso.eml"))

        assert tx is not None
        assert tx.amount == Decimal("92990")
        assert tx.transaction_type == TransactionType.debit
        assert tx.merchant == "Colombia Telecomunicaciones S.A. E.S.P. (Movil)"
        assert tx.category is None
        assert tx.currency == "COP"
        assert tx.is_pairing_candidate is False
        # "El 6 de abril de 2026 Hora: 2:28 p. m." Bogotá → 19:28 UTC
        assert tx.occurred_at == datetime(2026, 4, 6, 19, 28, tzinfo=timezone.utc)

    def test_pago_exitoso_after_midnight(self, parser: NequiParser) -> None:
        """"12:47 a. m." is 00:47, not 12:47."""
        tx = parser.parse(load_eml_fixture("nequi/pago_exitoso_madrugada.eml"))

        assert tx is not None
        assert tx.amount == Decimal("24700")
        assert tx.merchant == "PATRIMONIOS AUTONOMOS AVAL FIDUCIARIA S.A"
        # 5 ago 00:47 Bogotá → 05:47 UTC
        assert tx.occurred_at == datetime(2026, 8, 5, 5, 47, tzinfo=timezone.utc)

    @pytest.mark.parametrize(
        ("fixture", "merchant", "amount"),
        [
            ("nequi/comprobante_enel.eml", "Enel", "92670"),
            ("nequi/comprobante_claro.eml", "Claro Hogar", "92101"),
        ],
    )
    def test_comprobante_de_factura(
        self, parser: NequiParser, fixture: str, merchant: str, amount: str
    ) -> None:
        envelope = load_eml_fixture(fixture)
        tx = parser.parse(envelope)

        assert tx is not None
        assert tx.amount == Decimal(amount)
        assert tx.transaction_type == TransactionType.debit
        assert tx.merchant == merchant
        # No time in the body — falls back to when the email arrived.
        assert tx.occurred_at == envelope.received_at.astimezone(timezone.utc)

    def test_login_notice_from_payments_sender_returns_none(self, parser: NequiParser) -> None:
        assert parser.parse(load_eml_fixture("nequi/acceso_somos.eml")) is None


class TestUnrecognized:
    def test_unrecognized_body_returns_none(self, parser: NequiParser) -> None:
        envelope = EmailEnvelope(
            sender="notificaciones@nequi.com.co",
            subject="Notificación de acceso a tu Nequi",
            message_id="<y@nequi.com.co>",
            received_at=datetime.now(timezone.utc),
            html_body="<html><body>Alguien entró a tu cuenta desde un nuevo dispositivo.</body></html>",
        )
        assert parser.parse(envelope) is None

    def test_no_html_body_returns_none(self, parser: NequiParser) -> None:
        envelope = EmailEnvelope(
            sender="notificaciones@nequi.com.co",
            subject="¡Recibiste plata por Bre-B!",
            message_id="<z@nequi.com.co>",
            received_at=datetime.now(timezone.utc),
            html_body=None,
        )
        assert parser.parse(envelope) is None


def test_sync_query_includes_both_nequi_senders() -> None:
    from app.services.email_sync import build_query

    query = build_query([NequiParser()], last_sync_at=None, fallback_lookback_days=30)

    assert "from:notificaciones@nequi.com.co" in query
    assert "from:somos@nequi.com.co" in query
