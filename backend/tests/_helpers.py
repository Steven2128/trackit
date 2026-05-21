"""Shared test helpers — load .eml fixtures into EmailEnvelope instances."""

from __future__ import annotations

import email
from datetime import datetime, timezone
from email import policy
from email.utils import parsedate_to_datetime
from pathlib import Path

from app.parsers.base import EmailEnvelope

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_eml_fixture(relative_path: str) -> EmailEnvelope:
    """Load a .eml fixture from tests/fixtures/ and return an EmailEnvelope.

    Example: load_eml_fixture("itau_co/compra_debito_sector9.eml")
    """
    eml_path = FIXTURES_DIR / relative_path
    with eml_path.open("rb") as f:
        msg = email.message_from_binary_file(f, policy=policy.default)

    sender = str(msg["From"] or "")
    subject = str(msg["Subject"] or "")
    message_id = str(msg["Message-ID"] or "")

    date_hdr = msg["Date"]
    if date_hdr:
        received_at = parsedate_to_datetime(str(date_hdr))
        if received_at.tzinfo is None:
            received_at = received_at.replace(tzinfo=timezone.utc)
    else:
        received_at = datetime.now(timezone.utc)

    html_body: str | None = None
    text_body: str | None = None

    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/html" and html_body is None:
                html_body = part.get_content()
            elif ctype == "text/plain" and text_body is None:
                text_body = part.get_content()
    else:
        if msg.get_content_type() == "text/html":
            html_body = msg.get_content()
        else:
            text_body = msg.get_content()

    return EmailEnvelope(
        sender=sender,
        subject=subject,
        message_id=message_id,
        received_at=received_at,
        html_body=html_body,
        text_body=text_body,
    )
