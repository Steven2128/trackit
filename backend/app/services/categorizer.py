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
"""

from __future__ import annotations

import re
import unicodedata
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


def categorize(merchant: str | None) -> str | None:
    if not merchant:
        return None
    text = _normalize(merchant)
    for rule in RULES:
        if rule.pattern.search(text):
            return rule.category
    return None
