from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import pytest

from app.core import oauth_return
from app.core.config import Settings


@pytest.fixture(autouse=True)
def _settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        oauth_return,
        "settings",
        Settings(web_return_origins="http://localhost:8081", web_app_host="trackit-web.onrender.com"),
    )


@pytest.mark.parametrize(
    "url",
    ["http://localhost:8081/", "https://trackit-web.onrender.com/", "https://trackit-web.onrender.com/x?y=1"],
)
def test_allowed_origins_pass(url: str) -> None:
    assert oauth_return.validate_web_return_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/",
        "http://trackit-web.onrender.com/",  # http, not https
        "https://trackit-web.onrender.com.evil.example/",
        "javascript:alert(1)",
        "/relative",
        "trackit://auth",
    ],
)
def test_other_origins_rejected(url: str) -> None:
    with pytest.raises(ValueError):
        oauth_return.validate_web_return_url(url)


def test_web_redirect_puts_tokens_in_fragment() -> None:
    target = oauth_return.build_return_redirect(
        {"return_url": "https://trackit-web.onrender.com/#old"},
        "auth",
        {"access_token": "a", "refresh_token": "r"},
    )
    parts = urlsplit(target)
    assert parts.query == ""
    assert parse_qs(parts.fragment) == {"kind": ["auth"], "access_token": ["a"], "refresh_token": ["r"]}
    assert target.startswith("https://trackit-web.onrender.com/#")


def test_native_redirect_uses_scheme() -> None:
    target = oauth_return.build_return_redirect(
        {"return_scheme": "trackit"}, "gmail-connected", {"status": "ok", "email": "a@b.co"}
    )
    assert target == "trackit://gmail-connected?status=ok&email=a%40b.co"
