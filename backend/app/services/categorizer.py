"""Rule-based categorization of transactions by merchant string.

A single pure function `categorize(merchant)` runs an ordered list of regex
rules against the merchant text and returns the first matching category
(or `None` if nothing matches). Matching is case-insensitive and ignores
accents, so `"Éxito"`, `"EXITO"`, and `"exito"` all hit the same rule.

Categories reserved for other layers (do NOT add rules for them here):
- `transfer`: set by `transfer_matcher.py` after pairing Itaú outbound
  debits with inbound Nequi/Daviplata/Falabella credits.
- `cash_withdrawal`: set directly by parsers when they detect an ATM
  withdrawal (channel = "Cajero").

Callers must skip categorization when `parsed.category` is already set,
so the parser/matcher decisions are not overwritten.

Users can add their own rules ("merchant contains D1 → mercado", table
`merchant_category_rules`). They run before the system rules — the user
knows that their D1 is groceries, the system only knows it's food.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class CategoryRule:
    pattern: re.Pattern[str]
    category: str


def _rule(keywords: list[str], category: str) -> CategoryRule:
    joined = "|".join(re.escape(k) for k in keywords)
    return CategoryRule(re.compile(rf"\b({joined})\b", re.IGNORECASE), category)


# Ordered: first match wins. Order matters when a merchant could plausibly
# hit two rules (e.g. "Rappi" is delivery → food, not shopping).
RULES: list[CategoryRule] = [
    _rule(
        [
            "carulla", "exito", "jumbo", "olimpica", "ara", "d1", "justo",
            "rappi", "ifood", "didi food",
            "mcdonald", "burger king", "dominos", "kfc", "subway",
            "restaurante", "panaderia", "cafeteria", "pizza", "heladeria",
        ],
        "food",
    ),
    _rule(
        [
            "uber", "cabify", "didi", "indriver", "beat",
            "terpel", "esso", "mobil", "texaco", "primax",
            "gasolina", "peaje", "transmilenio", "metro",
        ],
        "transport",
    ),
    _rule(
        [
            "epm", "codensa", "enel", "acueducto", "vanti", "gas natural",
            "claro", "movistar", "tigo", "etb", "wom", "directv",
        ],
        "bills",
    ),
    _rule(
        [
            "netflix", "spotify", "disney", "hbo", "max", "amazon prime",
            "apple.com", "icloud", "google", "youtube", "paramount", "crunchyroll",
        ],
        "subscriptions",
    ),
    _rule(
        [
            "mercadolibre", "mercado libre", "amazon", "linio", "dafiti",
            "falabella", "homecenter", "easy", "ikea",
        ],
        "shopping",
    ),
    _rule(
        [
            "farmatodo", "cruz verde", "la rebaja", "drogas",
            "colsanitas", "sura", "sanitas", "compensar", "clinica",
        ],
        "health",
    ),
    _rule(
        [
            "cine colombia", "royal films", "procinal", "bar ", "discoteca",
            "teatro", "concierto",
        ],
        "entertainment",
    ),
]


def _normalize(text: str) -> str:
    """Strip accents so `Éxito`/`exito` collapse to the same string."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


@dataclass(frozen=True)
class UserRule:
    pattern: str  # normalized with `normalize_pattern`, e.g. "d1"
    category: str


_NON_WORD = re.compile(r"[^a-z0-9]+")
# Bank prefixes/suffixes around the merchant name ("COMPRA … A As").
_NOISE = {"compra", "a", "as", "pago", "pse"}


def normalize_pattern(text: str) -> str:
    """Lowercase, accent-free words separated by single spaces — the form
    both user patterns and merchants are compared in."""
    return _NON_WORD.sub(" ", _normalize(text).lower()).strip()


def match_user_rule(merchant: str | None, rules: Sequence[UserRule]) -> str | None:
    """Category of the most specific (longest) user pattern found as whole
    words in the merchant, or None."""
    if not merchant or not rules:
        return None
    text = f" {normalize_pattern(merchant)} "
    for rule in sorted(rules, key=lambda r: len(r.pattern), reverse=True):
        if rule.pattern and f" {rule.pattern} " in text:
            return rule.category
    return None


def system_category(merchant: str | None) -> str | None:
    """The built-in rules only (what an untouched transaction would have)."""
    if not merchant:
        return None
    text = _normalize(merchant)
    for rule in RULES:
        if rule.pattern.search(text):
            return rule.category
    return None


def categorize(merchant: str | None, user_rules: Sequence[UserRule] = ()) -> str | None:
    return match_user_rule(merchant, user_rules) or system_category(merchant)


def suggest_pattern(merchant: str | None) -> str | None:
    """What a new user rule should match for this merchant: the system
    keyword when one hits ("TIENDA D1 LA FLORIDA" → "d1", so every D1 branch
    matches), otherwise the first words of the name without bank noise or
    branch numbers ("EMPANADAS DEL TOLIMA LA 90" → "empanadas del tolima")."""
    if not merchant:
        return None
    text = _normalize(merchant)
    for rule in RULES:
        hit = rule.pattern.search(text)
        if hit:
            return normalize_pattern(hit.group(1))
    words = [
        w for w in normalize_pattern(merchant).split()
        if w not in _NOISE and not w.isdigit()
    ]
    return " ".join(words[:3]) or None


def follows_new_rule(
    merchant: str | None,
    current: str | None,
    target: str,
    rules: Sequence[UserRule],
    previous: str | None = None,
) -> bool:
    """Should an existing transaction move to ``target`` now that the rule
    exists ("apply to past")? Only when the rules route it there and nobody
    chose its category by hand: it still has what the system rules gave it,
    or what the same rule gave it before being changed (``previous``)."""
    if current == target or categorize(merchant, rules) != target:
        return False
    return current == system_category(merchant) or (previous is not None and current == previous)
