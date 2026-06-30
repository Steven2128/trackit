"""Unit tests for the rule-based categorizer.

The categorizer is a pure function — no DB, no async — so these tests
just feed merchant strings and assert the resulting category. The cases
mirror the kinds of strings Itaú's email parser yields in
`merchant` (raw store names from the email body).
"""

from __future__ import annotations

import pytest

from app.services.categorizer import categorize


@pytest.mark.parametrize(
    "merchant,expected",
    [
        # food
        ("CARULLA 134", "food"),
        ("Éxito Centro Mayor", "food"),
        ("EXITO EXPRESS", "food"),
        ("Rappi Colombia", "food"),
        ("McDonald's", "food"),
        ("Restaurante La Esquina", "food"),
        # transport
        ("Uber Trip", "transport"),
        ("Cabify Bogota", "transport"),
        ("ESTACION TERPEL", "transport"),
        ("Peaje Andes", "transport"),
        # bills
        ("EPM SERVICIOS", "bills"),
        ("Claro Movil", "bills"),
        ("Movistar Co", "bills"),
        # subscriptions
        ("NETFLIX.COM", "subscriptions"),
        ("Spotify P12345", "subscriptions"),
        ("APPLE.COM/BILL", "subscriptions"),
        # shopping
        ("MercadoLibre CO", "shopping"),
        ("Amazon Marketplace", "shopping"),
        ("HOMECENTER", "shopping"),
        # health
        ("FARMATODO 7", "health"),
        ("Cruz Verde Norte", "health"),
        ("Clinica del Country", "health"),
        # entertainment
        ("Cine Colombia Andino", "entertainment"),
        ("Bar La Noche", "entertainment"),
    ],
)
def test_categorize_returns_expected_category(merchant: str, expected: str) -> None:
    assert categorize(merchant) == expected


def test_categorize_unknown_merchant_returns_none() -> None:
    assert categorize("FERRETERIA DON JOSE") is None


def test_categorize_none_merchant_returns_none() -> None:
    assert categorize(None) is None


def test_categorize_empty_merchant_returns_none() -> None:
    assert categorize("") is None


def test_categorize_is_accent_insensitive() -> None:
    assert categorize("Éxito") == categorize("exito") == "food"


def test_categorize_is_case_insensitive() -> None:
    assert categorize("netflix") == categorize("NETFLIX") == "subscriptions"
