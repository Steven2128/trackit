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

    def test_rejects_marketing_senders(self, parser: NequiParser) -> None:
        for sender in ("somos@nequi.com.co", "somos@notificaciones.nequi.com.co"):
            envelope = EmailEnvelope(
                sender=sender,
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
        assert tx.category is None
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
        """Money from someone else's Bancolombia is income, not a self-transfer."""
        envelope = load_eml_fixture("nequi/recibiste_otro_banco.eml")
        tx = parser.parse(envelope)

        assert tx is not None
        assert tx.amount == Decimal("80000")
        assert tx.transaction_type == TransactionType.credit
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
