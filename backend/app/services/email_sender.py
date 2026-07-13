"""Outbound email via the Resend REST API — no SDK, no SMTP.

Sandbox sender (`onboarding@resend.dev`, the default `weekly_summary_from_email`)
only delivers to the email of the Resend account itself; a verified custom
domain is required to send to arbitrary recipients.
"""

from __future__ import annotations

import httpx

from app.core.config import settings

RESEND_API_URL = "https://api.resend.com/emails"


async def send_email(to: str, subject: str, html: str) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            RESEND_API_URL,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={
                "from": settings.weekly_summary_from_email,
                "to": [to],
                "subject": subject,
                "html": html,
            },
        )
        response.raise_for_status()
