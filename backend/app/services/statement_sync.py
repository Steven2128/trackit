"""Coordinate the monthly-statement reconciliation for a single
``ProviderConnection``: find the Itaú statement email, download the PDF
attachment, extract movement rows, and reconcile them against the DB.

Separate flow from `sync_provider_connection` (per-transaction sync) —
statement emails arrive monthly, aren't per-transaction parseable, and use
their own watermark (`last_statement_sync_at`) so the two syncs don't step
on each other's cursor.

The PDF carries no machine-readable period (see gotcha in
`app/parsers/itau_statement.py`), so the statement's month/year is derived
from the email's received date: Itaú sends the closing statement for month
M during the first days of month M+1, so we take the month *before* the
email arrived.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.integrations.gmail import gmail_message_to_envelope
from app.models.provider_connection import ProviderConnection
from app.parsers.base import EmailAttachment, EmailEnvelope
from app.parsers.itau_statement import extract_statement
from app.services.email_sync import build_gmail_client
from app.services.statement_reconciler import reconcile_rows

log = logging.getLogger(__name__)

STATEMENT_SENDER = "extractos@clienteitau.co"


@dataclass
class StatementSyncResult:
    processed: int = 0
    accounts_reconciled: int = 0
    matched: int = 0
    inserted: int = 0
    skipped_no_attachment: int = 0
    errors: int = 0
    last_statement_sync_at: datetime | None = None


def is_statement_email(envelope: EmailEnvelope) -> bool:
    return STATEMENT_SENDER.lower() in envelope.sender.lower()


def find_pdf_attachment(envelope: EmailEnvelope) -> EmailAttachment | None:
    for attachment in envelope.attachments:
        if attachment.filename.lower().endswith(".pdf"):
            return attachment
    return None


def _statement_period(received_at: datetime) -> tuple[int, int]:
    """Return (year, month) of the statement period for an email received at
    ``received_at`` — the closing statement for month M arrives early in
    month M+1."""
    if received_at.month == 1:
        return received_at.year - 1, 12
    return received_at.year, received_at.month - 1


async def sync_statements(
    db: AsyncSession,
    connection: ProviderConnection,
    *,
    fallback_lookback_days: int,
    max_messages: int,
) -> StatementSyncResult:
    client = build_gmail_client(connection)

    if connection.last_statement_sync_at is not None:
        epoch = int(connection.last_statement_sync_at.timestamp())
        query = f"from:{STATEMENT_SENDER} after:{epoch}"
    else:
        query = f"from:{STATEMENT_SENDER} newer_than:{fallback_lookback_days}d"

    log.info("statement_sync query=%s max_messages=%s", query, max_messages)
    message_ids = await asyncio.to_thread(client.list_message_ids, query, max_messages)

    result = StatementSyncResult()
    for message_id in message_ids:
        result.processed += 1
        try:
            raw_message = await asyncio.to_thread(client.get_message, message_id)
            envelope = gmail_message_to_envelope(raw_message)
            if not is_statement_email(envelope):
                continue

            attachment = find_pdf_attachment(envelope)
            if attachment is None:
                log.info(
                    "statement_sync no_pdf_attachment message_id=%s subject=%s",
                    message_id, envelope.subject,
                )
                result.skipped_no_attachment += 1
                continue

            pdf_bytes = await asyncio.to_thread(
                client.get_attachment, message_id, attachment.attachment_id
            )
            year, month = _statement_period(envelope.received_at)
            sections = extract_statement(
                pdf_bytes,
                statement_year=year,
                statement_month=month,
                password=settings.itau_statement_pdf_password or None,
            )

            for section in sections:
                if not section.rows:
                    continue
                reconciled = await reconcile_rows(
                    db, connection, section.account, section.rows, dry_run=False
                )
                result.accounts_reconciled += 1
                result.matched += reconciled.matched
                result.inserted += reconciled.inserted
        except Exception:  # noqa: BLE001 — one bad statement email must not abort the run
            log.exception("statement_sync error message_id=%s", message_id)
            result.errors += 1

    connection.last_statement_sync_at = datetime.now(timezone.utc)
    result.last_statement_sync_at = connection.last_statement_sync_at
    await db.commit()

    return result
