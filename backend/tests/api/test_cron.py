from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import cron
from app.core.config import settings


@pytest.fixture
def client() -> TestClient:
    # Bare app with only the cron router — avoids the scheduler lifespan.
    app = FastAPI()
    app.include_router(cron.router)
    return TestClient(app)


@pytest.fixture
def secret():
    with patch.object(settings, "cron_secret", "s3cret"):
        yield "s3cret"


def test_disabled_without_secret(client: TestClient) -> None:
    with patch.object(settings, "cron_secret", ""):
        resp = client.post("/internal/cron/gmail-sync", headers={"Authorization": "Bearer x"})
    assert resp.status_code == 404


def test_rejects_wrong_secret(client: TestClient, secret: str) -> None:
    resp = client.post("/internal/cron/gmail-sync", headers={"Authorization": "Bearer nope"})
    assert resp.status_code == 401


def test_rejects_missing_header(client: TestClient, secret: str) -> None:
    assert client.post("/internal/cron/gmail-sync").status_code == 401


def test_unknown_job(client: TestClient, secret: str) -> None:
    resp = client.post("/internal/cron/nope", headers={"Authorization": f"Bearer {secret}"})
    assert resp.status_code == 404


def test_runs_job(client: TestClient, secret: str) -> None:
    job = AsyncMock()
    with patch.dict(cron._JOBS, {"gmail-sync": job}):
        resp = client.post(
            "/internal/cron/gmail-sync", headers={"Authorization": f"Bearer {secret}"}
        )
    assert resp.status_code == 200
    assert resp.json() == {"job": "gmail-sync", "status": "done"}
    job.assert_awaited_once()
