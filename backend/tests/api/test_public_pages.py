from __future__ import annotations

from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import public_pages
from app.core.config import settings


def test_home_and_privacy_are_public() -> None:
    app = FastAPI()
    app.include_router(public_pages.router)
    client = TestClient(app)
    for path in ("/", "/privacy"):
        resp = client.get(path)
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]


def test_site_verification_meta_tag() -> None:
    app = FastAPI()
    app.include_router(public_pages.router)
    client = TestClient(app)
    assert "google-site-verification" not in client.get("/").text
    with patch.object(settings, "google_site_verification", "abc123"):
        body = client.get("/").text
    assert "<meta name='google-site-verification' content='abc123'>" in body
