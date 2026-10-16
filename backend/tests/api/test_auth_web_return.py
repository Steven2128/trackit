from __future__ import annotations

from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import auth
from app.core.config import settings
from app.core.security import decode_state_token


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(auth.router)
    return TestClient(app, follow_redirects=False)


def test_login_start_rejects_foreign_return_url() -> None:
    resp = _client().get("/auth/google/start", params={"return_url": "https://evil.example/"})
    assert resp.status_code == 400


def test_login_start_binds_web_return_url_to_state() -> None:
    with (
        patch.object(settings, "web_return_origins", "http://localhost:8081"),
        patch.object(auth, "build_authorization_url", side_effect=lambda **kw: f"https://google/?state={kw['state']}"),
    ):
        resp = _client().get("/auth/google/start", params={"return_url": "http://localhost:8081/"})
    assert resp.status_code == 307
    state = resp.headers["location"].split("state=", 1)[1]
    claims = decode_state_token(state)
    assert claims["return_url"] == "http://localhost:8081/"
    assert "return_scheme" not in claims
