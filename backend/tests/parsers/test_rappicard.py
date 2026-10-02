from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.models.transaction import TransactionType
from app.parsers.cards import CARD_FORMATS, CardEvent, CardEventKind, RappiCardParser
from app.schemas.debt import DebtCreate
from app.services.email_sync import (
    apply_card_event_to_balance,
    build_query,
    card_event_to_transaction,
    pick_card_debt,
)
from app.services.transfer_matcher import DEBT_PAYMENT_WINDOW, pair_transfers
from tests._helpers import load_eml_fixture

NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def parser() -> RappiCardParser:
    return RappiCardParser()


def _debt(**overrides) -> SimpleNamespace:
    base = dict(
        id=uuid.uuid4(),
        bank_name="RappiCard",
        total_amount=Decimal("100000"),
        email_sender="noreply@rappicard.co",
        email_format="rappicard",
        card_last_digits=None,
        email_linked_at=NOW,
        minimum_payment=None,
        payment_due_date=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _event(kind: CardEventKind, amount: str = "50000", **kw) -> CardEvent:
    return CardEvent(kind=kind, occurred_at=kw.pop("occurred_at", NOW + timedelta(hours=1)),
                     amount=Decimal(amount), **kw)


class TestRappiCardParser:
    def test_registered_as_card_format(self) -> None:
        assert isinstance(CARD_FORMATS["rappicard"], RappiCardParser)

    def test_compra(self, parser: RappiCardParser) -> None:
        event = parser.parse(load_eml_fixture("rappicard/compra.eml"))

        assert event is not None
        assert event.kind is CardEventKind.purchase
        assert event.amount == Decimal("24550")
        assert event.merchant == "Oxxo"
        assert event.card_last_digits == "1234"
        # "2026-09-04 13:55:3x" Bogotá → 18:55 UTC
        assert event.occurred_at.replace(second=0) == datetime(
            2026, 9, 4, 18, 55, tzinfo=timezone.utc
        )

    def test_comprobante_de_pago_uses_received_time(self, parser: RappiCardParser) -> None:
        """The body's "Fecha y hora" runs ~5h behind the funding bank debit."""
        envelope = load_eml_fixture("rappicard/comprobante_pago.eml")
        event = parser.parse(envelope)

        assert event is not None
        assert event.kind is CardEventKind.payment
        assert event.amount == Decimal("384000")
        assert event.occurred_at == envelope.received_at.astimezone(timezone.utc)

    def test_extracto(self, parser: RappiCardParser) -> None:
        event = parser.parse(load_eml_fixture("rappicard/extracto.eml"))

        assert event is not None
        assert event.kind is CardEventKind.statement
        assert event.minimum_payment == Decimal("92392.00")
        assert event.payment_due_date == date(2026, 9, 20)

    def test_marketing_returns_none(self, parser: RappiCardParser) -> None:
        assert parser.parse(load_eml_fixture("rappicard/contrato_firmado.eml")) is None


class TestPickCardDebt:
    def test_single_linked_debt_takes_everything(self) -> None:
        debt = _debt()
        for kind in CardEventKind:
            assert pick_card_debt([debt], _event(kind)) is debt

    def test_purchase_routes_by_card_digits(self) -> None:
        a, b = _debt(card_last_digits="1111"), _debt(card_last_digits="2222")
        event = _event(CardEventKind.purchase, card_last_digits="2222")
        assert pick_card_debt([a, b], event) is b

    def test_purchase_on_unknown_card_of_a_digit_bound_debt_is_skipped(self) -> None:
        debt = _debt(card_last_digits="1111")
        event = _event(CardEventKind.purchase, card_last_digits="9999")
        assert pick_card_debt([debt], event) is None

    def test_payment_is_ambiguous_with_two_cards(self) -> None:
        a, b = _debt(card_last_digits="1111"), _debt(card_last_digits="2222")
        assert pick_card_debt([a, b], _event(CardEventKind.payment)) is None


class TestBalance:
    def test_purchase_raises_and_payment_lowers(self) -> None:
        debt = _debt()
        apply_card_event_to_balance(debt, _event(CardEventKind.purchase, "30000"))
        assert debt.total_amount == Decimal("130000")
        apply_card_event_to_balance(debt, _event(CardEventKind.payment, "50000"))
        assert debt.total_amount == Decimal("80000")

    def test_payment_never_goes_below_zero(self) -> None:
        debt = _debt(total_amount=Decimal("10000"))
        apply_card_event_to_balance(debt, _event(CardEventKind.payment, "50000"))
        assert debt.total_amount == Decimal("0")

    def test_movements_before_linking_are_history_only(self) -> None:
        debt = _debt()
        old = _event(CardEventKind.purchase, "30000", occurred_at=NOW - timedelta(days=3))
        apply_card_event_to_balance(debt, old)
        assert debt.total_amount == Decimal("100000")


class TestCardTransactions:
    def _connection(self) -> SimpleNamespace:
        return SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4())

    def test_purchase_is_categorized_spending_linked_to_debt(self) -> None:
        debt = _debt()
        event = _event(CardEventKind.purchase, merchant="RAPPI", card_last_digits="1234")

        tx = card_event_to_transaction(event, debt, self._connection(), "msg-1")

        assert tx.transaction_type == TransactionType.debit
        assert tx.category == "food"
        assert tx.debt_id == debt.id
        assert tx.raw_email_reference == "msg-1"

    def test_payment_is_debt_payment_credit_and_pairing_candidate(self) -> None:
        debt = _debt()
        tx = card_event_to_transaction(_event(CardEventKind.payment), debt, self._connection(), "m")

        assert tx.transaction_type == TransactionType.credit
        assert tx.category == "debt_payment"
        assert tx.merchant == "Pago RappiCard"
        assert tx.is_pairing_candidate is True

    def test_payment_pairs_with_funding_bank_debit(self) -> None:
        """Davivienda PSE debit at 01:20:19, RappiCard receipt at 01:20:35."""
        base = datetime(2026, 9, 5, 1, 20, 19, tzinfo=timezone.utc)
        debit = SimpleNamespace(id=uuid.uuid4(), amount=Decimal("384000"), occurred_at=base)
        receipt = SimpleNamespace(
            id=uuid.uuid4(), amount=Decimal("384000"), occurred_at=base + timedelta(seconds=16)
        )
        assert pair_transfers([debit], [receipt], window=DEBT_PAYMENT_WINDOW) == [
            (debit.id, receipt.id)
        ]


def test_sync_query_includes_linked_card_senders() -> None:
    query = build_query(
        [], last_sync_at=None, fallback_lookback_days=30,
        extra_senders=[" NoReply@RappiCard.co "],
    )
    assert query == "from:noreply@rappicard.co newer_than:30d"


class TestDebtSchema:
    def test_sender_is_normalized(self) -> None:
        debt = DebtCreate(
            bank_name="RappiCard", total_amount=Decimal("1"),
            email_sender="  NoReply@RappiCard.co ", email_format="rappicard",
        )
        assert debt.email_sender == "noreply@rappicard.co"

    @pytest.mark.parametrize("field,value", [("email_sender", "no-es-email"), ("card_last_digits", "12a4")])
    def test_rejects_invalid_link_fields(self, field: str, value: str) -> None:
        with pytest.raises(ValidationError):
            DebtCreate(bank_name="X", total_amount=Decimal("1"), **{field: value})
