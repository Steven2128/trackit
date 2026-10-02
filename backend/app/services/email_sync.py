"""Coordinate a Gmail sync run for a single ``ProviderConnection``.

End-to-end flow per call:

1. Decrypt the stored OAuth tokens.
2. Build a ``GmailClient`` with an ``on_token_refresh`` callback that
   re-encrypts and writes the new access token + expiry back to the
   connection row (commit happens at the end with the transaction batch).
3. Compute the Gmail search window. First sync: ``newer_than:Nd``.
   Subsequent syncs: ``after:<epoch>`` using ``last_sync_at``.
4. List candidate message IDs filtered by the senders that registered
   parsers care about (``EmailParser.sender_filter``) plus the credit-card
   senders the user linked to a ``Debt`` from the app.
5. For each ID: skip if we already stored it (dedupe by
   ``raw_email_reference``), otherwise fetch + dispatch. Card senders go to
   the debt's card format (``app/parsers/cards``) and move its balance; the
   rest go to the first matching bank parser. Persist a ``Transaction``.
6. Update ``last_sync_at`` and commit, then pair transfers and card payments.

Failures in a single message (parser raised, decode failed) are logged and
counted in ``SyncResult.errors`` — they never abort the whole sync.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_token, encrypt_token
from app.integrations.gmail import (
    GmailClient,
    GmailCredentials,
    gmail_message_to_envelope,
)
from app.models.debt import Debt
from app.models.provider_connection import ProviderConnection
from app.models.transaction import Transaction, TransactionType
from app.parsers import REGISTERED_PARSERS
from app.parsers.cards import CARD_FORMATS, CardEvent, CardEventKind
from app.services.categorizer import categorize
from app.services.transfer_matcher import match_debt_payments, match_transfers
from app.parsers.base import EmailEnvelope, EmailParser, ParsedTransaction

log = logging.getLogger(__name__)


@dataclass
class SyncResult:
    processed: int = 0
    created: int = 0
    skipped_duplicate: int = 0
    skipped_no_parser: int = 0
    skipped_parser_returned_none: int = 0
    card_statements: int = 0
    errors: int = 0
    last_sync_at: datetime | None = None


def build_gmail_client(connection: ProviderConnection) -> GmailClient:
    """Decrypt the stored OAuth tokens and build a `GmailClient` for
    ``connection``, wiring a refresh callback that re-encrypts and stages
    the new access token on the connection row (caller commits). Shared by
    the per-transaction sync (`sync_provider_connection`) and the statement
    sync (`app/services/statement_sync.py`)."""
    if not connection.refresh_token_encrypted:
        raise RuntimeError("provider_connection has no refresh token stored")

    access_token = decrypt_token(connection.access_token_encrypted)
    refresh_token = decrypt_token(connection.refresh_token_encrypted)

    def _persist_refreshed_token(new_token: str, new_expiry: datetime | None) -> None:
        connection.access_token_encrypted = encrypt_token(new_token)
        connection.expires_at = new_expiry

    return GmailClient(
        GmailCredentials(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=connection.expires_at,
        ),
        on_token_refresh=_persist_refreshed_token,
    )


async def sync_provider_connection(
    db: AsyncSession,
    connection: ProviderConnection,
    *,
    fallback_lookback_days: int,
    max_messages: int,
) -> SyncResult:
    client = build_gmail_client(connection)
    card_debts = await load_card_debts(db, connection.user_id)

    query = build_query(
        REGISTERED_PARSERS,
        last_sync_at=connection.last_sync_at,
        fallback_lookback_days=fallback_lookback_days,
        extra_senders=[d.email_sender for d in card_debts if d.email_sender],
    )
    log.info("gmail_sync query=%s max_messages=%s", query, max_messages)

    message_ids = await asyncio.to_thread(client.list_message_ids, query, max_messages)

    result = SyncResult()
    for message_id in message_ids:
        result.processed += 1
        try:
            await _process_message(db, client, connection, message_id, result, card_debts)
        except Exception:  # noqa: BLE001 — never abort the batch on one bad email
            log.exception("gmail_sync parser_error message_id=%s", message_id)
            result.errors += 1

    connection.last_sync_at = datetime.now(timezone.utc)
    result.last_sync_at = connection.last_sync_at
    await db.commit()

    try:
        await match_transfers(db, connection.user_id)
        await match_debt_payments(db, connection.user_id)
    except Exception:  # noqa: BLE001 — pairing is best-effort, never fail the sync
        log.exception("transfer_matcher failed user_id=%s", connection.user_id)

    return result


async def load_card_debts(db: AsyncSession, user_id) -> list[Debt]:
    """Debts linked to a credit-card email sender with a known format."""
    rows = await db.execute(
        select(Debt).where(
            Debt.user_id == user_id,
            Debt.email_sender.is_not(None),
            Debt.email_format.is_not(None),
        )
    )
    return [d for d in rows.scalars().all() if d.email_format in CARD_FORMATS]


async def _process_message(
    db: AsyncSession,
    client: GmailClient,
    connection: ProviderConnection,
    message_id: str,
    result: SyncResult,
    card_debts: Sequence[Debt] = (),
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

    sender = envelope.sender.lower()
    linked = [d for d in card_debts if d.email_sender and d.email_sender.lower() in sender]
    if linked:
        await _process_card_email(db, connection, envelope, message_id, linked, result)
        return

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

    # Savepoint per insert: a concurrent sync (manual + cron overlap) can win
    # the race after our dedupe SELECT; the unique index is the source of truth.
    try:
        async with db.begin_nested():
            db.add(_to_transaction(parsed, connection, fallback_message_id=message_id))
            await db.flush()
    except IntegrityError:
        result.skipped_duplicate += 1
        return
    result.created += 1


async def _process_card_email(
    db: AsyncSession,
    connection: ProviderConnection,
    envelope: EmailEnvelope,
    message_id: str,
    linked: list[Debt],
    result: SyncResult,
) -> None:
    event = CARD_FORMATS[linked[0].email_format].parse(envelope)
    if event is None:
        log.info("gmail_sync card_skipped message_id=%s", message_id)
        result.skipped_parser_returned_none += 1
        return

    debt = pick_card_debt(linked, event)
    if debt is None:
        log.info("gmail_sync card_unmatched message_id=%s", message_id)
        result.skipped_parser_returned_none += 1
        return

    if event.kind is CardEventKind.statement:
        if debt.payment_due_date is None or event.payment_due_date >= debt.payment_due_date:
            debt.minimum_payment = event.minimum_payment
            debt.payment_due_date = event.payment_due_date
        result.card_statements += 1
        return

    tx = card_event_to_transaction(event, debt, connection, message_id)
    try:
        async with db.begin_nested():
            db.add(tx)
            await db.flush()
    except IntegrityError:
        result.skipped_duplicate += 1
        return
    apply_card_event_to_balance(debt, event)
    result.created += 1


def pick_card_debt(linked: list[Debt], event: CardEvent) -> Debt | None:
    """Several cards can share a sender: purchases carry the card digits;
    payments/statements don't, so they only resolve when one debt is linked."""
    if event.kind is CardEventKind.purchase and event.card_last_digits:
        exact = [d for d in linked if d.card_last_digits == event.card_last_digits]
        if exact:
            return exact[0]
        linked = [d for d in linked if not d.card_last_digits]
    return linked[0] if len(linked) == 1 else None


def card_event_to_transaction(
    event: CardEvent,
    debt: Debt,
    connection: ProviderConnection,
    message_id: str,
) -> Transaction:
    if event.kind is CardEventKind.purchase:
        # Real spending, counted the day it happens; categorized like any purchase.
        return Transaction(
            user_id=connection.user_id,
            provider_connection_id=connection.id,
            amount=event.amount,
            merchant=event.merchant,
            category=categorize(event.merchant),
            transaction_type=TransactionType.debit,
            currency="COP",
            card_last_digits=event.card_last_digits,
            occurred_at=event.occurred_at,
            raw_email_reference=message_id,
            debt_id=debt.id,
        )
    # Card payment: neither income nor spending. The matcher pairs it with the
    # bank debit that funded it and re-tags that debit "debt_payment" too.
    return Transaction(
        user_id=connection.user_id,
        provider_connection_id=connection.id,
        amount=event.amount,
        merchant=f"Pago {debt.bank_name}",
        category="debt_payment",
        transaction_type=TransactionType.credit,
        currency="COP",
        occurred_at=event.occurred_at,
        raw_email_reference=message_id,
        is_pairing_candidate=True,
        debt_id=debt.id,
    )


def apply_card_event_to_balance(debt: Debt, event: CardEvent) -> None:
    """Purchases raise the balance, payments lower it (never below 0). Only
    movements after the user linked the sender count: the balance typed then
    already includes everything older."""
    if debt.email_linked_at is None or event.occurred_at < debt.email_linked_at:
        return
    if event.kind is CardEventKind.purchase:
        debt.total_amount = debt.total_amount + event.amount
    elif event.kind is CardEventKind.payment:
        debt.total_amount = max(debt.total_amount - event.amount, 0)


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
        is_pairing_candidate=parsed.is_pairing_candidate,
    )


def build_query(
    parsers: list[EmailParser],
    *,
    last_sync_at: datetime | None,
    fallback_lookback_days: int,
    extra_senders: Iterable[str] = (),
) -> str:
    senders = sorted(
        {
            s.lower()
            for p in parsers
            if p.sender_filter
            for s in (
                (p.sender_filter,) if isinstance(p.sender_filter, str) else p.sender_filter
            )
        }
        | {s.strip().lower() for s in extra_senders if s and s.strip()}
    )
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
