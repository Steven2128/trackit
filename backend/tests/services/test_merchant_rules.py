"""User merchant rules on top of the built-in categorizer. Merchant strings
are the real shapes the Davivienda/Itaú/RappiCard parsers produce."""

from __future__ import annotations

import pytest

from app.services.categorizer import (
    UserRule,
    categorize,
    follows_new_rule,
    match_user_rule,
    normalize_pattern,
    suggest_pattern,
)

D1_MERCADO = UserRule(pattern="d1", category="mercado")


@pytest.mark.parametrize(
    "merchant",
    ["TIENDA D1 LA FLORIDA", "COMPRA TIENDA D1 LA FLORIDA A As", "TIENDAS D1 MED TARAPAC"],
)
def test_user_rule_beats_the_system_rule(merchant) -> None:
    assert categorize(merchant) == "food"
    assert categorize(merchant, [D1_MERCADO]) == "mercado"


def test_rule_matches_whole_words_only() -> None:
    # "d1" must not fire inside another token.
    assert match_user_rule("TIENDA AD10 CENTRO", [D1_MERCADO]) is None


def test_no_rule_match_falls_back_to_the_system() -> None:
    assert categorize("RAPPI COLOMBIA*DL", [D1_MERCADO]) == "food"
    assert categorize("Uber Trip", [D1_MERCADO]) == "transport"


def test_longest_pattern_wins() -> None:
    rules = [D1_MERCADO, UserRule(pattern="d1 la florida", category="galguerias")]
    assert categorize("TIENDA D1 LA FLORIDA", rules) == "galguerias"
    assert categorize("TIENDAS D1 MED TARAPAC", rules) == "mercado"


def test_matching_ignores_case_accents_and_symbols() -> None:
    rules = [UserRule(pattern=normalize_pattern("Heladería"), category="galguerias")]
    assert categorize("COMPRA HELADERIA DIVERPLAZA", rules) == "galguerias"
    assert normalize_pattern("  RAPPI*Colombia  ") == "rappi colombia"


@pytest.mark.parametrize(
    "merchant,expected",
    [
        ("TIENDA D1 LA FLORIDA", "d1"),  # system keyword: covers every branch
        ("COMPRA TIENDAS ARA A As", "ara"),
        ("COMPRA DLO*DiDi Food CO Payin", "didi food"),
        ("EMPANADAS DEL TOLIMA LA 90", "empanadas del tolima"),  # no system hit
        ("COMPRA BERSHKA 0042 A As", "bershka"),
        ("", None),
        (None, None),
    ],
)
def test_suggest_pattern(merchant, expected) -> None:
    assert suggest_pattern(merchant) == expected


class TestFollowsNewRule:
    def test_untouched_transaction_moves(self) -> None:
        # Still has the system category ("food") → follows the rule.
        assert follows_new_rule("TIENDA D1 LA FLORIDA", "food", "mercado", [D1_MERCADO])

    def test_hand_categorized_transaction_stays(self) -> None:
        # The user said this D1 run was snacks; the rule must not undo it.
        assert not follows_new_rule("TIENDA D1 LA FLORIDA", "galguerias", "mercado", [D1_MERCADO])

    def test_other_merchants_are_not_touched(self) -> None:
        assert not follows_new_rule("RAPPI COLOMBIA*DL", "food", "mercado", [D1_MERCADO])

    def test_already_in_target_is_not_counted(self) -> None:
        assert not follows_new_rule("TIENDA D1 LA FLORIDA", "mercado", "mercado", [D1_MERCADO])

    def test_changing_a_rule_moves_what_it_had_moved(self) -> None:
        rule = UserRule(pattern="d1", category="hogar")
        assert follows_new_rule("TIENDA D1", "mercado", "hogar", [rule], previous="mercado")

    def test_a_more_specific_rule_keeps_its_transactions(self) -> None:
        rules = [D1_MERCADO, UserRule(pattern="d1 la florida", category="galguerias")]
        assert not follows_new_rule("TIENDA D1 LA FLORIDA", "food", "mercado", rules)


def test_synced_emails_use_the_user_rules() -> None:
    """email_sync wiring: bank and card purchases both go through the rules;
    a category the parser decided (transfer) is never overridden."""
    import uuid
    from datetime import datetime, timezone
    from decimal import Decimal
    from types import SimpleNamespace

    from app.models.transaction import TransactionType
    from app.parsers.base import ParsedTransaction
    from app.parsers.cards.base import CardEvent, CardEventKind
    from app.services.email_sync import _to_transaction, card_event_to_transaction

    connection = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4())
    now = datetime(2026, 10, 18, 17, tzinfo=timezone.utc)

    def parsed(merchant, category=None):
        return ParsedTransaction(
            amount=Decimal("45000"), merchant=merchant, transaction_type=TransactionType.debit,
            currency="COP", occurred_at=now, raw_email_reference="m1", category=category,
        )

    bank = _to_transaction(
        parsed("TIENDA D1 LA FLORIDA"), connection, fallback_message_id="m1",
        source="davivienda", user_rules=[D1_MERCADO],
    )
    assert bank.category == "mercado"
    transfer = _to_transaction(
        parsed("TIENDA D1", category="transfer"), connection, fallback_message_id="m2",
        user_rules=[D1_MERCADO],
    )
    assert transfer.category == "transfer"

    event = CardEvent(kind=CardEventKind.purchase, occurred_at=now, amount=Decimal("29900"),
                      merchant="Tiendas D1", card_last_digits="4875")
    debt = SimpleNamespace(id=uuid.uuid4(), bank_name="RappiCard")
    card = card_event_to_transaction(event, debt, connection, "m3", [D1_MERCADO])
    assert card.category == "mercado"
