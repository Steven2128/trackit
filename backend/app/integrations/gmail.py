"""Real Gmail client backed by google-api-python-client.

We deliberately keep this module thin: it knows how to talk to Gmail and how
to convert a Gmail API message dict into the ``EmailEnvelope`` the parsers
expect. Anything domain-specific (queries, sender filters, persistence) lives
in ``app/services/email_sync.py`` instead.

Token refresh: the underlying ``google.oauth2.credentials.Credentials`` object
refreshes the access token transparently when an API call fires with an expired
token. We snapshot the token/expiry before each call and invoke
``on_token_refresh`` if either changed, so the caller can persist the new pair.
"""

from __future__ import annotations

import base64
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.core.config import settings
from app.parsers.base import EmailAttachment, EmailEnvelope

GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GMAIL_API_SCOPES = ("https://www.googleapis.com/auth/gmail.readonly",)


TokenRefreshCallback = Callable[[str, datetime | None], None]


@dataclass
class GmailCredentials:
    access_token: str
    refresh_token: str | None = None
    expires_at: datetime | None = None
    scopes: tuple[str, ...] = field(default_factory=lambda: GMAIL_API_SCOPES)


class GmailClient:
    """Gmail v1 REST client scoped to a single user's credentials."""

    def __init__(
        self,
        credentials: GmailCredentials,
        *,
        on_token_refresh: TokenRefreshCallback | None = None,
    ) -> None:
        self._on_refresh = on_token_refresh
        self._creds = Credentials(
            token=credentials.access_token,
            refresh_token=credentials.refresh_token,
            token_uri=GOOGLE_TOKEN_URI,
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            scopes=list(credentials.scopes),
            expiry=_strip_tz(credentials.expires_at),
        )
        self._service = build(
            "gmail",
            "v1",
            credentials=self._creds,
            cache_discovery=False,
        )

    def list_message_ids(self, query: str, max_results: int) -> list[str]:
        """Return up to ``max_results`` Gmail message IDs matching ``query``."""
        ids: list[str] = []
        page_token: str | None = None
        users = self._service.users()
        with self._refresh_guard():
            while len(ids) < max_results:
                remaining = max_results - len(ids)
                page_size = min(remaining, 100)
                request = users.messages().list(
                    userId="me",
                    q=query,
                    maxResults=page_size,
                    pageToken=page_token,
                )
                response = request.execute()
                for entry in response.get("messages", []):
                    ids.append(entry["id"])
                    if len(ids) >= max_results:
                        break
                page_token = response.get("nextPageToken")
                if not page_token:
                    break
        return ids

    def get_message(self, message_id: str) -> dict[str, Any]:
        with self._refresh_guard():
            return (
                self._service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )

    def get_attachment(self, message_id: str, attachment_id: str) -> bytes:
        """Fetch attachment bytes — Gmail only inlines small parts; larger
        ones (like statement PDFs) require this separate call."""
        with self._refresh_guard():
            response = (
                self._service.users()
                .messages()
                .attachments()
                .get(userId="me", messageId=message_id, id=attachment_id)
                .execute()
            )
        return base64.urlsafe_b64decode(response["data"].encode("ascii"))

    def _refresh_guard(self) -> _RefreshGuard:
        return _RefreshGuard(self._creds, self._on_refresh)


class _RefreshGuard:
    """Context manager: snapshots token/expiry, fires callback on change."""

    def __init__(
        self,
        creds: Credentials,
        on_refresh: TokenRefreshCallback | None,
    ) -> None:
        self._creds = creds
        self._on_refresh = on_refresh
        self._token_before: str | None = None
        self._expiry_before: datetime | None = None

    def __enter__(self) -> "_RefreshGuard":
        self._token_before = self._creds.token
        self._expiry_before = self._creds.expiry
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        if self._on_refresh is None:
            return
        if self._creds.token == self._token_before and self._creds.expiry == self._expiry_before:
            return
        new_expiry = self._creds.expiry
        if new_expiry is not None and new_expiry.tzinfo is None:
            new_expiry = new_expiry.replace(tzinfo=timezone.utc)
        self._on_refresh(self._creds.token, new_expiry)


def gmail_message_to_envelope(msg: dict[str, Any]) -> EmailEnvelope:
    """Convert a Gmail ``messages.get(format=full)`` response into ``EmailEnvelope``."""
    payload = msg.get("payload", {})
    headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}

    sender = headers.get("from", "")
    subject = headers.get("subject", "")
    message_id = headers.get("message-id", msg.get("id", ""))

    received_at = _parse_date_header(headers.get("date")) or _from_internal_date(
        msg.get("internalDate")
    )

    html_body, text_body = _extract_bodies(payload)
    attachments = _extract_attachments(payload)

    return EmailEnvelope(
        sender=sender,
        subject=subject,
        message_id=message_id,
        received_at=received_at,
        html_body=html_body,
        text_body=text_body,
        attachments=attachments,
    )


def _extract_bodies(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    """Walk a Gmail payload tree and return (html_body, text_body)."""
    html_body: str | None = None
    text_body: str | None = None

    for part in _walk_parts(payload):
        mime = part.get("mimeType", "")
        data = part.get("body", {}).get("data")
        if not data:
            continue
        decoded = _decode_part_body(data, _part_charset(part))
        if mime == "text/html" and html_body is None:
            html_body = decoded
        elif mime == "text/plain" and text_body is None:
            text_body = decoded
        if html_body and text_body:
            break

    return html_body, text_body


def _extract_attachments(payload: dict[str, Any]) -> list[EmailAttachment]:
    """Walk a Gmail payload tree and collect attachment metadata (no bytes —
    fetch those on demand via `GmailClient.get_attachment`)."""
    attachments: list[EmailAttachment] = []
    for part in _walk_parts(payload):
        filename = part.get("filename") or ""
        attachment_id = part.get("body", {}).get("attachmentId")
        if not filename or not attachment_id:
            continue
        attachments.append(
            EmailAttachment(
                filename=filename,
                mime_type=part.get("mimeType", ""),
                attachment_id=attachment_id,
                size=part.get("body", {}).get("size", 0),
            )
        )
    return attachments


def _walk_parts(part: dict[str, Any]) -> Iterable[dict[str, Any]]:
    yield part
    for child in part.get("parts", []) or []:
        yield from _walk_parts(child)


def _part_charset(part: dict[str, Any]) -> str | None:
    """Charset from the part's Content-Type header, if declared."""
    for header in part.get("headers", []) or []:
        if header.get("name", "").lower() == "content-type":
            match = re.search(r'charset="?([\w.:-]+)"?', header.get("value", ""), re.IGNORECASE)
            if match:
                return match.group(1)
    return None


def _decode_part_body(data: str, charset: str | None = None) -> str:
    """Decode a body part. Honors the declared charset, then falls back to
    UTF-8 and finally cp1252 — Davivienda sends Latin-1 bodies, and a blind
    UTF-8 decode turned every accent into U+FFFD."""
    raw = base64.urlsafe_b64decode(data.encode("ascii"))
    for encoding in (charset, "utf-8"):
        if not encoding:
            continue
        try:
            return raw.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("cp1252", errors="replace")


def _parse_date_header(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _from_internal_date(internal_date: str | None) -> datetime:
    if internal_date is None:
        return datetime.now(timezone.utc)
    try:
        millis = int(internal_date)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)
    return datetime.fromtimestamp(millis / 1000, tz=timezone.utc)


def _strip_tz(value: datetime | None) -> datetime | None:
    """google-auth's Credentials.expiry is naive UTC; coerce timezone-aware input."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)
