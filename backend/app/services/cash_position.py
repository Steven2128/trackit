"""Biweekly cash position: how much of today's money is really free.

Pure, DB-free core (same shape as cash_flow / debt_strategy); the DB
wrapper comes later. The bank balance is never "money to spend": part of it
belongs to someone else, part is due before the next payday, part is the
groceries of this fortnight and part has to wait for bills the next payday
can't cover.

    own  = Σ account balances − money held for others
    X_0  = own − C_0 − E_0
    X_k  = X_{k−1} + I_k − C_k − E_k
    free = min(X_0 … X_K)          reserve_for_later = X_0 − free

Windows: W_0 runs from today to the first expected income, W_k from one
expected income to the next. C_k = what is still owed on obligations due in
W_k, E_k = essential spending planned for the fortnights that start in W_k,
I_k = income expected at the start of W_k.

Rules that keep it honest:
- Expected income is never money today: I_0 = 0, and since free ≤ X_0 a
  future payday can only spare a reserve, never add free money.
- An obligation due the same day as an income counts in the window before
  it (the deposit may land late in the day, or late) — unless the user
  pays those with that payday (``pay_due_on_payday``: "lo del 5 se paga
  con la del 5").
- An expected income whose day passed without arriving counts as arriving
  tomorrow and is flagged late.
- Paying an obligation lowers the balance and what's owed by the same
  amount, so ``free`` doesn't move; nothing is reserved twice. (Paying
  *ahead* — something due after the next payday — can lower today's
  ``free``: it spends cash an earlier window needed.)
- Missing data never becomes a number: an obligation with no amount and no
  upper bound (or a hold of unknown size) makes the result "indeterminate";
  estimates and bounds make it "provisional".

Fortnights ("quincenas") follow paydays: days 5–19 and 20–4, local dates,
half-open so no day is in two of them.
"""

from __future__ import annotations

import calendar
import enum
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from decimal import Decimal

ZERO = Decimal("0")
# Spent share of a discretionary budget that makes a purchase "tight".
TIGHT_BUDGET_SHARE = Decimal("0.80")


# --- Fortnights and paydays ---


def fortnight_bounds(day: date) -> tuple[date, date]:
    """[start, end) of the fortnight containing ``day``: 5–19 or 20–4."""
    if 5 <= day.day < 20:
        return day.replace(day=5), day.replace(day=20)
    if day.day >= 20:
        return day.replace(day=20), _add_months(day.replace(day=5), 1)
    return _add_months(day.replace(day=20), -1), day.replace(day=5)


def fortnight_starts(after: date, before: date) -> list[date]:
    """Fortnight start days d with after < d < before."""
    starts = []
    current = fortnight_bounds(after)[1]
    while current < before:
        starts.append(current)
        current = fortnight_bounds(current)[1]
    return starts


def payday(year: int, month: int, day: int) -> date:
    """When a deposit nominally due on ``day`` lands: weekends move it to the
    Friday before (observed: the 20-Sep-2026 payroll, a Sunday, arrived on
    Friday the 18th). Day 31 in a short month is its last day."""
    d = date(year, month, min(day, calendar.monthrange(year, month)[1]))
    if d.weekday() >= 5:
        d -= timedelta(days=d.weekday() - 4)
    return d


def _add_months(d: date, months: int) -> date:
    index = d.year * 12 + d.month - 1 + months
    return d.replace(year=index // 12, month=index % 12 + 1)


# --- Inputs ---


class AmountStatus(str, enum.Enum):
    confirmed = "confirmed"
    estimated = "estimated"
    unknown = "unknown"


@dataclass(frozen=True)
class Hold:
    """Money in the user's accounts that isn't theirs to spend (a sibling's
    share of the rent). ``amount`` None = the user hasn't said how much."""

    name: str
    amount: Decimal | None


@dataclass(frozen=True)
class ExpectedIncome:
    """A deposit that hasn't arrived yet (received ones are already in the
    balance and must not be passed)."""

    name: str
    amount: Decimal
    on: date
    estimated: bool = True


@dataclass(frozen=True)
class Obligation:
    """One due date of something to pay (rent of this cycle, one card
    statement). ``amount`` None with an ``upper_bound`` = "at most this"
    (a card minimum can't exceed the balance); with neither it's unknown."""

    name: str
    due: date | None
    amount: Decimal | None = None
    status: AmountStatus = AmountStatus.confirmed
    upper_bound: Decimal | None = None
    paid: Decimal = ZERO
    # Opaque id the caller uses to act on it ("planned:<uuid>", "debt:<uuid>").
    ref: str | None = None


@dataclass(frozen=True)
class Essential:
    """Basic spending planned per fortnight (groceries). ``per_fortnight``
    None = no figure yet (transport): tracked, flagged, never invented."""

    category: str
    per_fortnight: Decimal | None
    spent_this_fortnight: Decimal = ZERO


@dataclass(frozen=True)
class DiscretionaryBudget:
    """Fortnight cap on a treat category (snacks, clothes)."""

    category: str
    limit: Decimal
    spent: Decimal = ZERO


@dataclass(frozen=True)
class PositionInputs:
    today: date
    # Last day looked at. Obligations due that day count; a fortnight that
    # starts on it is left to its own payday.
    horizon_end: date
    balance: Decimal
    holds: tuple[Hold, ...] = ()
    incomes: tuple[ExpectedIncome, ...] = ()
    obligations: tuple[Obligation, ...] = ()
    essentials: tuple[Essential, ...] = ()
    budgets: tuple[DiscretionaryBudget, ...] = ()
    # True: what's due on a payday is paid with that payday's money.
    pay_due_on_payday: bool = False


# --- Result ---


class PositionStatus(str, enum.Enum):
    confirmed = "confirmed"
    provisional = "provisional"  # uses estimates or upper bounds
    indeterminate = "indeterminate"  # something that matters is unknown


@dataclass
class WindowLine:
    name: str
    amount: Decimal  # still owed
    estimated: bool = False
    due: date | None = None
    total: Decimal = ZERO  # what the due date asks for; paid = total − amount
    ref: str | None = None


@dataclass
class Window:
    start: date
    end: date | None  # exclusive; None = open until the horizon
    income: Decimal = ZERO
    income_names: list[str] = field(default_factory=list)
    obligations: list[WindowLine] = field(default_factory=list)
    essentials: Decimal = ZERO
    balance_after: Decimal = ZERO  # X_k

    @property
    def committed(self) -> Decimal:
        return sum((o.amount for o in self.obligations), ZERO)


@dataclass
class Deficit:
    window_start: date
    amount: Decimal  # how far below zero that window ends
    obligations: list[str]


@dataclass
class Position:
    status: PositionStatus
    balance: Decimal
    held_for_others: Decimal
    own: Decimal
    due_before_next_income: Decimal  # C_0
    essentials_until_next_income: Decimal  # E_0
    reserve_for_later: Decimal  # X_0 − free
    free: Decimal  # may be negative = deficit
    budget_remaining: Decimal | None  # Σ discretionary caps left
    spendable_now: Decimal  # min(free, budget_remaining), never negative
    windows: list[Window]
    deficit: Deficit | None = None
    missing: list[str] = field(default_factory=list)  # → indeterminate
    estimated: list[str] = field(default_factory=list)  # → provisional
    late_incomes: list[str] = field(default_factory=list)
    overdue: list[str] = field(default_factory=list)
    no_plan: list[str] = field(default_factory=list)  # essentials without a figure


# --- Core ---


def compute_position(inp: PositionInputs) -> Position:
    missing: list[str] = []
    estimated: list[str] = []
    late: list[str] = []
    overdue: list[str] = []
    no_plan: list[str] = []

    held = ZERO
    for hold in inp.holds:
        if hold.amount is None:
            missing.append(f"{hold.name}: cuánto es")
        else:
            held += hold.amount

    # Window boundaries = days an expected income lands (never today: a
    # late income is assumed to land tomorrow).
    tomorrow = inp.today + timedelta(days=1)
    incomes_by_day: dict[date, list[ExpectedIncome]] = {}
    for income in inp.incomes:
        on = income.on
        if on <= inp.today:
            late.append(income.name)
            on = tomorrow
        if on > inp.horizon_end:
            continue
        incomes_by_day.setdefault(on, []).append(income)
        if income.estimated:
            estimated.append(f"{income.name} (ingreso estimado)")
    boundaries = sorted(incomes_by_day)

    windows = [Window(start=inp.today, end=boundaries[0] if boundaries else None)]
    for i, day in enumerate(boundaries):
        group = incomes_by_day[day]
        windows.append(
            Window(
                start=day,
                end=boundaries[i + 1] if i + 1 < len(boundaries) else None,
                income=sum((g.amount for g in group), ZERO),
                income_names=[g.name for g in group],
            )
        )

    def window_for_due(due: date | None) -> int:
        # Strictly-before count: due on an income day → the window before.
        if due is None or due <= inp.today:
            return 0
        if inp.pay_due_on_payday:
            return sum(1 for b in boundaries if b <= due)
        return sum(1 for b in boundaries if b < due)

    def window_for_start(day: date) -> int:
        return sum(1 for b in boundaries if b <= day)

    for ob in inp.obligations:
        if ob.due is not None and ob.due > inp.horizon_end:
            continue
        if ob.amount is not None:
            owed = ob.amount
            is_estimate = ob.status is not AmountStatus.confirmed
        elif ob.upper_bound is not None:
            owed = ob.upper_bound
            is_estimate = True
        else:
            missing.append(f"{ob.name}: monto")
            continue
        remaining = max(owed - ob.paid, ZERO)
        if remaining == 0:
            # Paid: never reserved again, but still listed (amount 0) so the
            # plan shows it done.
            windows[window_for_due(ob.due)].obligations.append(
                WindowLine(ob.name, ZERO, due=ob.due, total=owed, ref=ob.ref)
            )
            continue
        if is_estimate:
            estimated.append(
                f"{ob.name} (cota máxima)" if ob.amount is None else f"{ob.name} (estimado)"
            )
        if ob.due is None:
            # Placed in the earliest window, to be safe.
            is_estimate = True
            estimated.append(f"{ob.name} (fecha por confirmar)")
        elif ob.due < inp.today:
            overdue.append(ob.name)
        windows[window_for_due(ob.due)].obligations.append(
            WindowLine(
                ob.name, remaining, estimated=is_estimate, due=ob.due, total=owed, ref=ob.ref
            )
        )

    future_starts = fortnight_starts(inp.today, inp.horizon_end)
    for ess in inp.essentials:
        if ess.per_fortnight is None:
            no_plan.append(ess.category)
            continue
        # This fortnight: what's left of the plan (spending it lowers the
        # reserve one to one). Later fortnights: the whole plan.
        windows[0].essentials += max(ess.per_fortnight - ess.spent_this_fortnight, ZERO)
        for start in future_starts:
            windows[window_for_start(start)].essentials += ess.per_fortnight

    running = inp.balance - held
    for i, w in enumerate(windows):
        running = running + (w.income if i else ZERO) - w.committed - w.essentials
        w.balance_after = running

    x0 = windows[0].balance_after
    free = min(w.balance_after for w in windows)
    deficit = None
    if free < 0:
        first = next(w for w in windows if w.balance_after < 0)
        deficit = Deficit(
            window_start=first.start,
            amount=-first.balance_after,
            obligations=[o.name for o in first.obligations if o.amount],
        )

    budget_remaining = (
        sum((max(b.limit - b.spent, ZERO) for b in inp.budgets), ZERO) if inp.budgets else None
    )
    spendable = max(free, ZERO)
    if budget_remaining is not None:
        spendable = min(spendable, budget_remaining)

    if missing:
        status = PositionStatus.indeterminate
    elif estimated or late or no_plan:
        status = PositionStatus.provisional
    else:
        status = PositionStatus.confirmed

    return Position(
        status=status,
        balance=inp.balance,
        held_for_others=held,
        own=inp.balance - held,
        due_before_next_income=windows[0].committed,
        essentials_until_next_income=windows[0].essentials,
        reserve_for_later=x0 - free if free < x0 else ZERO,
        free=free,
        budget_remaining=budget_remaining,
        spendable_now=spendable,
        windows=windows,
        deficit=deficit,
        missing=missing,
        estimated=estimated,
        late_incomes=late,
        overdue=overdue,
        no_plan=no_plan,
    )


# --- "¿Puedo comprar esto?" ---


class Verdict(str, enum.Enum):
    viable = "viable"
    tight = "tight"  # ajustada
    not_advisable = "not_advisable"  # no recomendable
    indeterminate = "indeterminate"


@dataclass
class PurchaseCheck:
    verdict: Verdict
    before: Position
    after: Position
    reasons: list[str]


def simulate_purchase(
    inp: PositionInputs,
    amount: Decimal,
    category: str,
    *,
    card_due: date | None = None,
    cushion: Decimal = ZERO,
) -> PurchaseCheck:
    """Re-run the position as if the purchase happened today.

    Cash or debit (``card_due`` None): the balance drops now. Credit card:
    the balance doesn't move, but the full amount is reserved for the card's
    next due date — conservative, since how much the next minimum grows is
    unknown until the statement arrives (it then replaces this estimate, it
    doesn't add to it). Either way it counts against the category's budget
    or essential plan.
    """
    after_inp = replace(
        inp,
        essentials=tuple(
            replace(e, spent_this_fortnight=e.spent_this_fortnight + amount)
            if e.category == category
            else e
            for e in inp.essentials
        ),
        budgets=tuple(
            replace(b, spent=b.spent + amount) if b.category == category else b
            for b in inp.budgets
        ),
    )
    if card_due is None:
        after_inp = replace(after_inp, balance=inp.balance - amount)
    else:
        after_inp = replace(
            after_inp,
            obligations=(
                *inp.obligations,
                Obligation(
                    name=f"Tarjeta: esta compra ({category})",
                    due=card_due,
                    amount=amount,
                    status=AmountStatus.estimated,
                ),
            ),
        )

    before = compute_position(inp)
    after = compute_position(after_inp)
    reasons: list[str] = []
    budget = next((b for b in after_inp.budgets if b.category == category), None)

    if after.status is PositionStatus.indeterminate:
        reasons += [f"Falta: {m}" for m in after.missing]
        return PurchaseCheck(Verdict.indeterminate, before, after, reasons)

    if after.free < 0:
        reasons.append(f"Deja un faltante de {-after.free} antes de {after.deficit.window_start}")
    if budget is not None and budget.spent > budget.limit:
        reasons.append(f"Supera el tope de {category} ({budget.spent} de {budget.limit})")
    if reasons:
        return PurchaseCheck(Verdict.not_advisable, before, after, reasons)

    if after.free < cushion:
        reasons.append(f"Te quedan solo {after.free} libres")
    near_cap = budget is not None and budget.spent >= budget.limit * TIGHT_BUDGET_SHARE
    if budget is not None and budget.limit > 0 and near_cap:
        reasons.append(f"Llevás {budget.spent} de {budget.limit} en {category}")
    if reasons:
        return PurchaseCheck(Verdict.tight, before, after, reasons)
    return PurchaseCheck(Verdict.viable, before, after, reasons)
