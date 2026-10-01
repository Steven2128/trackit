from __future__ import annotations

import pytest

from app.core.config import Settings


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "postgresql+asyncpg://u:p@db:5432/trackit",
            "postgresql+asyncpg://u:p@db:5432/trackit",
        ),
        (
            "postgres://u:p@host/db",
            "postgresql+asyncpg://u:p@host/db",
        ),
        (
            "postgresql://u:p@ep-x.neon.tech/neondb?sslmode=require",
            "postgresql+asyncpg://u:p@ep-x.neon.tech/neondb?ssl=require",
        ),
        (
            "postgresql://u:p@ep-x.neon.tech/neondb?sslmode=require&channel_binding=require",
            "postgresql+asyncpg://u:p@ep-x.neon.tech/neondb?ssl=require",
        ),
        (
            "postgresql://u:p@ep-x.neon.tech/neondb?channel_binding=require&sslmode=require",
            "postgresql+asyncpg://u:p@ep-x.neon.tech/neondb?ssl=require",
        ),
    ],
)
def test_database_url_normalized(raw: str, expected: str) -> None:
    assert Settings(database_url=raw).database_url == expected
