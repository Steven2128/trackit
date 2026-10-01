from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import public_pages


def test_home_and_privacy_are_public() -> None:
    app = FastAPI()
    app.include_router(public_pages.router)
    client = TestClient(app)
    for path in ("/", "/privacy"):
        resp = client.get(path)
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
