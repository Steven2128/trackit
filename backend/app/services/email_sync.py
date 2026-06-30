"""Coordinate a Gmail sync run for a single ``ProviderConnection``.

End-to-end flow per call:

1. Decrypt the stored OAuth tokens.
2. Build a ``GmailClient`` with an ``on_token_refresh`` callback that
   re-encrypts and writes the new access token + expiry back to the
   connection row (commit happens at the end with the transaction batch).
3. Compute the Gmail search window. First sync: ``newer_than:Nd``.
   Subsequent syncs: ``after:<epoch>`` using ``last_sync_at``.
4. List candidate message IDs filtered by the senders that registered
   parsers care about (``EmailParser.sender_filter``).
5. For each ID: skip if we already stored it (dedupe by
   ``raw_email_reference``), otherwise fetch + dispatch to the first
   matching parser and persist a ``Transaction``.
6. Update ``last_sync_at`` and commit.

Failures in a single message (parser raised, decode failed) are logged and
counted in ``SyncResult.errors`` — they never abort the whole sync.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_token, encrypt_token
from app.integrations.gmail import (
    GmailClient,
    GmailCredentials,
    gmail_message_to_envelope,
)
from app.models.provider_connection import ProviderConnection
from app.models.transaction import Transaction
from app.parsers import REGISTERED_PARSERS
from app.services.categorizer import categorize
from app.parsers.base import EmailEnvelope, EmailParser, ParsedTransaction

log = logging.getLogger(__name__)


@dataclass
class SyncResult:
    processed: int = 0
    created: int = 0
    skipped_duplicate: int = 0
    skipped_no_parser: int = 0
    skipped_parser_returned_none: int = 0
    errors: int = 0
    last_sync_at: datetime | None = None


async def sync_provider_connection(
    db: AsyncSession,
    connection: ProviderConnection,
    *,
    fallback_lookback_days: int,
    max_messages: int,
) -> SyncResult:
    if not connection.refresh_token_encrypted:
        raise RuntimeError("provider_connection has no refresh token stored")

    access_token = decrypt_token(connection.access_token_encrypted)
    refresh_token = decrypt_token(connection.refresh_token_encrypted)

    def _persist_refreshed_token(new_token: str, new_expiry: datetime | None) -> None:
        connection.access_token_encrypted = encrypt_token(new_token)
        connection.expires_at = new_expiry

    client = GmailClient(
        GmailCredentials(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=connection.expires_at,
        ),
        on_token_refresh=_persist_refreshed_token,
    )

    query = build_query(
        REGISTERED_PARSERS,
        last_sync_at=connection.last_sync_at,
        fallback_lookback_days=fallback_lookback_days,
    )
    log.info("gmail_sync query=%s max_messages=%s", query, max_messages)

    message_ids = await asyncio.to_thread(client.list_message_ids, query, max_messages)

    result = SyncResult()
    for message_id in message_ids:
        result.processed += 1
        try:
            await _process_message(db, client, connection, message_id, result)
        except Exception:  # noqa: BLE001 — never abort the batch on one bad email
            log.exception("gmail_sync parser_error message_id=%s", message_id)
            result.errors += 1

    connection.last_sync_at = datetime.now(timezone.utc)
    result.last_sync_at = connection.last_sync_at
    await db.commit()
    return result


async def _process_message(
    db: AsyncSession,
    client: GmailClient,
    connection: ProviderConnection,
    message_id: str,
    result: SyncResult,
) -> None:
    existing = await db.execute(
        select(Transaction.id)
        .where(
            Transaction.provider_connection_id == connection.id,
            Transaction.raw_email_reference == message_id,
        )
        .limit(1)
    )
    if existing.scalar_one_or_none() is not None:
        result.skipped_duplicate += 1
        return

    raw_message = await asyncio.to_thread(client.get_message, message_id)
    envelope = gmail_message_to_envelope(raw_message)

    parser = _pick_parser(envelope)
    if parser is None:
        log.info(
            "gmail_sync unknown_sender message_id=%s sender=%s subject=%s",
            message_id,
            envelope.sender,
            envelope.subject,
        )
        result.skipped_no_parser += 1
        return

    parsed = parser.parse(envelope)
    if parsed is None:
        log.info("gmail_sync parser_skipped parser=%s message_id=%s", parser.name, message_id)
        result.skipped_parser_returned_none += 1
        return

    db.add(_to_transaction(parsed, connection, fallback_message_id=message_id))
    result.created += 1


def _pick_parser(envelope: EmailEnvelope) -> EmailParser | None:
    for parser in REGISTERED_PARSERS:
        if parser.can_parse(envelope):
            return parser
    return None


def _to_transaction(
    parsed: ParsedTransaction,
    connection: ProviderConnection,
    *,
    fallback_message_id: str,
) -> Transaction:
    category = parsed.category if parsed.category is not None else categorize(parsed.merchant)
    return Transaction(
        user_id=connection.user_id,
        provider_connection_id=connection.id,
        amount=parsed.amount,
        merchant=parsed.merchant,
        category=category,
        transaction_type=parsed.transaction_type,
        currency=parsed.currency,
        card_last_digits=parsed.card_last_digits,
        occurred_at=parsed.occurred_at,
        raw_email_reference=parsed.raw_email_reference or fallback_message_id,
    )


def build_query(
    parsers: list[EmailParser],
    *,
    last_sync_at: datetime | None,
    fallback_lookback_days: int,
) -> str:
    senders = sorted({p.sender_filter.lower() for p in parsers if p.sender_filter})
    if not senders:
        raise RuntimeError(
            "No parsers declare a sender_filter — cannot build a Gmail query"
        )

    from_clause = (
        f"from:{senders[0]}"
        if len(senders) == 1
        else "(" + " OR ".join(f"from:{s}" for s in senders) + ")"
    )

    if last_sync_at is not None:
        epoch = int(last_sync_at.timestamp())
        window_clause = f"after:{epoch}"
    else:
        window_clause = f"newer_than:{fallback_lookback_days}d"

    return f"{from_clause} {window_clause}"
