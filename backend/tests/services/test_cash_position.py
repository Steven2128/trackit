"""Biweekly cash position. Every amount here is FICTITIOUS, built to make
the formula easy to check by hand, not the user's data."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from app.services.cash_position import (
    DiscretionaryBudget,
    Essential,
    ExpectedIncome,
    Hold,
    Obligation,
    PositionInputs,
    PositionStatus,
    Verdict,
    compute_position,
    fortnight_bounds,
    payday,
    simulate_purchase,
)


def k(n) -> Decimal:
    """Thousands of pesos."""
    return Decimal(n) * 1000


RENT = Obligation("Arriendo", date(2026, 10, 24), k(1200))
CARD_NOW = Obligation("Tarjeta X (extracto)", date(2026, 10, 20), k(300))
INTERNET = Obligation("Internet", date(2026, 11, 1), k(50))
CARD_NEXT = Obligation("Tarjeta X (próximo)", date(2026, 11, 20), k(200))
MERCADO = Essential("mercado", k(150), spent_this_fortnight=k(60))
GUSTOS = DiscretionaryBudget("galguerias", k(200), spent=k(50))

# S0, the base state of the design: 15-Oct, 1.000 in hand, paydays of
# 1.000 on 20-Oct and 5-Nov.
S0 = PositionInputs(
    today=date(2026, 10, 15),
    horizon_end=date(2026, 11, 20),
    balance=k(1000),
    incomes=(
        ExpectedIncome("Quincena 20", k(1000), date(2026, 10, 20), estimated=False),
        ExpectedIncome("Quincena 5", k(1000), date(2026, 11, 5), estimated=False),
    ),
    obligations=(CARD_NOW, RENT, INTERNET, CARD_NEXT),
    essentials=(MERCADO,),
    budgets=(GUSTOS,),
)


# S1: the same plan on payday (20-Oct) — 15→19 followed the groceries plan
# and the 1.000 landed. Rent and internet are now due before the next payday.
S1 = replace(
    S0,
    today=date(2026, 10, 20),
    balance=k(1000) - k(90) + k(1000),
    incomes=(S0.incomes[1],),
    essentials=(Essential("mercado", k(150)),),
)


def with_obligation(inp: PositionInputs, name: str, **changes) -> PositionInputs:
    return replace(
        inp,
        obligations=tuple(
            replace(o, **changes) if o.name == name else o for o in inp.obligations
        ),
    )


def owed_lines(pos, name: str) -> list[Decimal]:
    return [o.amount for w in pos.windows for o in w.obligations if o.name == name]


# --- Base state ---


def test_base_state_matches_the_hand_calculation() -> None:
    pos = compute_position(S0)
    # X0 = 1000 − 300 (card, due on payday → before it) − 90 (groceries left)
    # X1 = 610 + 1000 − 1200 − 50 − 150 ; X2 = 210 + 1000 − 200 − 150
    assert [w.balance_after for w in pos.windows] == [k(610), k(210), k(860)]
    assert pos.due_before_next_income == k(300)
    assert pos.essentials_until_next_income == k(90)
    assert pos.free == k(210)
    assert pos.reserve_for_later == k(400)  # rent the 20th payday can't cover
    assert pos.budget_remaining == k(150)
    assert pos.spendable_now == k(150)
    assert pos.status is PositionStatus.confirmed
    assert pos.deficit is None


# --- Scenario 1: payday ---


def test_payday_short_by_20_lowers_free_by_exactly_20() -> None:
    # 15→19 spent the remaining 90 of groceries (balance 910), then 980
    # arrived instead of 1000. New fortnight: the groceries plan restarts.
    pos = compute_position(
        replace(
            S0,
            today=date(2026, 10, 20),
            balance=k(910) + k(980),
            incomes=(S0.incomes[1],),
            essentials=(Essential("mercado", k(150)),),
        )
    )
    # X0 = 1890 − 300 − 1200 − 50 − 150 ; X1 = 190 + 1000 − 200 − 150
    assert [w.balance_after for w in pos.windows] == [k(190), k(840)]
    assert pos.free == k(190)
    assert pos.reserve_for_later == 0


def test_income_exactly_as_expected_leaves_free_unchanged() -> None:
    assert compute_position(S1).free == compute_position(S0).free


# --- Scenarios 2–4: paying obligations never moves `free` ---


@pytest.mark.parametrize("paid", [k(1200), k(500), k(1), k(700)])
def test_paying_rent_in_full_or_part_keeps_free(paid) -> None:
    pos = compute_position(
        with_obligation(replace(S1, balance=S1.balance - paid), "Arriendo", paid=paid)
    )
    assert pos.free == compute_position(S1).free == k(210)
    remaining = k(1200) - paid
    assert owed_lines(pos, "Arriendo") == ([remaining] if remaining else [])


def test_overpaying_costs_exactly_the_excess() -> None:
    pos = compute_position(
        with_obligation(replace(S1, balance=S1.balance - k(1250)), "Arriendo", paid=k(1250))
    )
    assert pos.free == compute_position(S1).free - k(50)


def test_prepaying_before_payday_can_lower_todays_free_money() -> None:
    """Paying 500 of the rent on the 15th uses cash the card due on the 20th
    needed: the plan still closes, but only 110 can be spent today."""
    pos = compute_position(
        with_obligation(replace(S0, balance=S0.balance - k(500)), "Arriendo", paid=k(500))
    )
    assert [w.balance_after for w in pos.windows][:2] == [k(110), k(210)]
    assert pos.free == k(110)


def test_paid_obligation_is_never_reserved_again() -> None:
    pos = compute_position(with_obligation(S0, "Internet", paid=k(50)))
    assert owed_lines(pos, "Internet") == []


def test_card_payment_from_the_bank_keeps_free() -> None:
    """Both the bank debit and the payment recorded = neither recorded (the
    receipt arrived but the bank email didn't): the balance stays high and
    the obligation stays owed, and they cancel out the same way."""
    paid = compute_position(
        with_obligation(
            replace(S0, balance=S0.balance - k(300)), "Tarjeta X (extracto)", paid=k(300)
        )
    )
    assert paid.free == compute_position(S0).free
    assert paid.due_before_next_income == 0


# --- Scenarios 5–6: spending ---


def test_groceries_within_plan_keep_free() -> None:
    pos = compute_position(
        replace(
            S0,
            balance=S0.balance - k(40),
            essentials=(replace(MERCADO, spent_this_fortnight=k(100)),),
        )
    )
    assert pos.free == compute_position(S0).free


def test_groceries_over_plan_cost_the_overrun() -> None:
    pos = compute_position(
        replace(
            S0,
            balance=S0.balance - k(120),
            essentials=(replace(MERCADO, spent_this_fortnight=k(180)),),
        )
    )
    assert pos.free == k(180)  # 30 over the plan


def test_card_snack_reserves_for_the_card_due_date_not_today() -> None:
    check = simulate_purchase(S0, k(30), "galguerias", card_due=date(2026, 11, 20))
    assert check.after.balance == S0.balance  # no cash leaves today
    assert check.after.windows[2].balance_after == k(830)  # paid from the 5-Nov window
    assert check.after.free == k(210)
    assert check.after.budget_remaining == k(120)  # but it counts as a treat now
    assert check.verdict is Verdict.viable


def test_card_purchase_due_before_next_payday_hits_free() -> None:
    check = simulate_purchase(S0, k(30), "galguerias", card_due=date(2026, 10, 30))
    assert check.after.free == k(180)


# --- Scenario 7: own transfer ---


def test_transfer_between_own_accounts_changes_nothing() -> None:
    # Only the total enters: bank 600 → 400, wallet 400 → 600.
    moved = replace(S0, balance=k(400) + k(600))
    assert compute_position(moved).free == compute_position(S0).free


# --- Scenario 8: statement not known yet ---


def test_unknown_statement_makes_the_result_indeterminate() -> None:
    inp = replace(
        S0, obligations=(*S0.obligations, Obligation("Banco de Bogotá", date(2026, 10, 30)))
    )
    pos = compute_position(inp)
    assert pos.status is PositionStatus.indeterminate
    assert pos.missing == ["Banco de Bogotá: monto"]


def test_statement_with_an_upper_bound_is_provisional_and_conservative() -> None:
    inp = replace(
        S0,
        obligations=(
            *S0.obligations,
            Obligation("Banco de Bogotá", date(2026, 10, 30), upper_bound=k(250)),
        ),
    )
    pos = compute_position(inp)
    assert pos.status is PositionStatus.provisional
    assert pos.free == k(-40)
    assert pos.deficit.window_start == date(2026, 10, 20)
    assert "Banco de Bogotá (cota máxima)" in pos.estimated


# --- Scenario 9: payday that can't cover what's coming ---


def test_deficit_names_the_window_and_what_is_due() -> None:
    pos = compute_position(with_obligation(S0, "Arriendo", amount=k(1600)))
    assert pos.free == k(-190)
    assert pos.deficit.window_start == date(2026, 10, 20)
    assert pos.deficit.amount == k(190)
    assert "Arriendo" in pos.deficit.obligations
    assert pos.spendable_now == 0


# --- Scenario 10: "¿Puedo comprar esto?" ---


def test_purchase_verdicts() -> None:
    assert simulate_purchase(S0, k(20), "galguerias").verdict is Verdict.viable
    tight = simulate_purchase(S0, k(120), "galguerias")  # 170 of 200 = 85%
    assert tight.verdict is Verdict.tight
    over = simulate_purchase(S0, k(180), "galguerias")  # 230 of 200
    assert over.verdict is Verdict.not_advisable
    assert over.after.free == k(30)  # affordable, but over the cap
    broke = simulate_purchase(S0, k(400), "ropa")  # no cap, but breaks the rent
    assert broke.verdict is Verdict.not_advisable
    assert broke.after.free == k(-190)


def test_purchase_with_missing_data_is_indeterminate() -> None:
    inp = replace(S0, holds=(Hold("Hermano", None),))
    check = simulate_purchase(inp, k(20), "galguerias")
    assert check.verdict is Verdict.indeterminate
    assert check.reasons == ["Falta: Hermano: cuánto es"]


def test_cushion_makes_a_purchase_tight() -> None:
    check = simulate_purchase(S0, k(150), "ropa", cushion=k(100))
    assert check.after.free == k(60)
    assert check.verdict is Verdict.tight


# --- Scenario 11: recategorizing ---


def test_moving_groceries_to_snacks_reserves_groceries_again() -> None:
    pos = compute_position(
        replace(
            S0,
            essentials=(replace(MERCADO, spent_this_fortnight=k(20)),),
            budgets=(replace(GUSTOS, spent=k(90)),),
        )
    )
    assert pos.free == k(170)
    assert pos.budget_remaining == k(110)


# --- Scenario 12: fortnight boundaries ---


@pytest.mark.parametrize(
    "day,expected",
    [
        (date(2026, 10, 19), (date(2026, 10, 5), date(2026, 10, 20))),
        (date(2026, 10, 20), (date(2026, 10, 20), date(2026, 11, 5))),
        (date(2026, 11, 4), (date(2026, 10, 20), date(2026, 11, 5))),
        (date(2026, 11, 5), (date(2026, 11, 5), date(2026, 11, 20))),
        (date(2026, 12, 25), (date(2026, 12, 20), date(2027, 1, 5))),
        (date(2027, 1, 3), (date(2026, 12, 20), date(2027, 1, 5))),
        (date(2027, 2, 20), (date(2027, 2, 20), date(2027, 3, 5))),
    ],
)
def test_fortnight_bounds(day, expected) -> None:
    assert fortnight_bounds(day) == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        ((2026, 9, 20), date(2026, 9, 18)),  # Sunday → Friday (observed)
        ((2026, 12, 5), date(2026, 12, 4)),  # Saturday → Friday
        ((2026, 10, 20), date(2026, 10, 20)),  # Tuesday stays
        ((2026, 2, 31), date(2026, 2, 27)),  # → 28 (Saturday) → Friday 27
    ],
)
def test_payday(args, expected) -> None:
    assert payday(*args) == expected


def test_new_fortnight_restarts_the_groceries_plan() -> None:
    last_day = compute_position(replace(S0, today=date(2026, 10, 19)))
    assert last_day.essentials_until_next_income == k(90)
    first_day = compute_position(
        replace(
            S0,
            today=date(2026, 10, 20),
            incomes=(S0.incomes[1],),
            essentials=(Essential("mercado", k(150)),),
        )
    )
    assert first_day.essentials_until_next_income == k(150)


# --- Other rules ---


def test_money_held_for_someone_else_is_not_free() -> None:
    pos = compute_position(replace(S0, holds=(Hold("Hermano (arriendo)", k(150)),)))
    assert pos.own == k(850)
    assert pos.free == k(60)


def test_using_held_money_for_its_purpose_keeps_free() -> None:
    """Rent paid with a sibling's share: balance, hold and the user's own
    share of the rent all drop together."""
    held = replace(
        S1,
        balance=S1.balance + k(550),
        holds=(Hold("Hermano (arriendo)", k(550)),),
    )
    # The landlord gets 1.750: the user's 1.200 and the sibling's 550.
    paid = replace(
        with_obligation(held, "Arriendo", paid=k(1200)),
        balance=held.balance - k(1750),
        holds=(Hold("Hermano (arriendo)", Decimal("0")),),
    )
    assert compute_position(paid).free == compute_position(held).free == k(210)


def test_future_income_never_raises_free_above_what_is_in_hand() -> None:
    rich = replace(
        S0,
        incomes=(*S0.incomes, ExpectedIncome("Prima", k(9000), date(2026, 10, 25))),
    )
    pos = compute_position(rich)
    assert pos.free <= pos.windows[0].balance_after


def test_late_income_is_assumed_tomorrow_and_flagged() -> None:
    pos = compute_position(
        replace(
            S0,
            today=date(2026, 10, 21),
            obligations=(Obligation("Movistar", date(2026, 10, 22), k(30)),),
            essentials=(),
            budgets=(),
        )
    )
    assert pos.late_incomes == ["Quincena 20"]
    assert pos.status is PositionStatus.provisional
    # Due tomorrow = the day the late payroll is now expected → before it.
    assert pos.due_before_next_income == k(30)


def test_obligation_without_a_date_goes_first() -> None:
    pos = compute_position(with_obligation(S0, "Internet", due=None))
    assert pos.windows[0].committed == k(350)
    assert "Internet (fecha por confirmar)" in pos.estimated


def test_overdue_obligation_is_flagged_and_due_now() -> None:
    pos = compute_position(with_obligation(S0, "Internet", due=date(2026, 10, 10)))
    assert pos.overdue == ["Internet"]
    assert pos.due_before_next_income == k(350)


def test_essential_without_a_plan_is_flagged_not_invented() -> None:
    pos = compute_position(replace(S0, essentials=(MERCADO, Essential("transporte", None))))
    assert pos.no_plan == ["transporte"]
    assert pos.status is PositionStatus.provisional
    assert pos.free == k(210)


def test_obligations_after_the_horizon_are_ignored() -> None:
    far_bill = Obligation("Lejano", date(2027, 1, 15), k(5000))
    pos = compute_position(replace(S0, obligations=(*S0.obligations, far_bill)))
    assert pos.free == k(210)


def test_paying_what_is_due_on_payday_with_that_payday() -> None:
    """The user's rule: the card due on the 20th is paid with the 20th."""
    pos = compute_position(replace(S0, pay_due_on_payday=True))
    assert pos.due_before_next_income == 0
    assert "Tarjeta X (extracto)" in [o.name for o in pos.windows[1].obligations]
    # Same money overall, just one window later: X0 610+300, X1 unchanged.
    assert [w.balance_after for w in pos.windows] == [k(910), k(210), k(860)]
