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
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decrypt_token, encrypt_token
from app.integrations.gmail import (
    GmailClient,
    GmailCredentials,
    gmail_message_to_envelope,
)
from app.models.debt import Debt
from app.models.merchant_category_rule import MerchantCategoryRule
from app.models.provider_connection import ProviderConnection
from app.models.transaction import Transaction, TransactionType
from app.parsers import REGISTERED_PARSERS
from app.parsers.cards import CARD_FORMATS, CardEvent, CardEventKind
from app.parsers.cards.rappicard_statement import extract_statement
from app.services.card_statement import apply_card_statement
from app.services.categorizer import UserRule, categorize
from app.services.net_worth import CASH_SOURCE, keep_cash_reconciled
from app.services.transfer_matcher import (
    match_debt_payments,
    match_transfers,
    reconcile_receipts,
)
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
    user_rules = await load_user_rules(db, connection.user_id)

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
            await _process_message(
                db, client, connection, message_id, result, card_debts, user_rules
            )
        except Exception:  # noqa: BLE001 — never abort the batch on one bad email
            log.exception("gmail_sync parser_error message_id=%s", message_id)
            result.errors += 1

    connection.last_sync_at = datetime.now(timezone.utc)
    result.last_sync_at = connection.last_sync_at
    await db.commit()

    try:
        # Receipts first: the merged bank debit can then pair with a card receipt.
        await reconcile_receipts(db, connection.user_id)
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


async def load_user_rules(db: AsyncSession, user_id) -> list[UserRule]:
    """The user's own merchant → category rules (run before the system ones)."""
    rows = await db.execute(
        select(MerchantCategoryRule.pattern, MerchantCategoryRule.category).where(
            MerchantCategoryRule.user_id == user_id
        )
    )
    return [UserRule(pattern=p, category=c) for p, c in rows.all()]


async def _process_message(
    db: AsyncSession,
    client: GmailClient,
    connection: ProviderConnection,
    message_id: str,
    result: SyncResult,
    card_debts: Sequence[Debt] = (),
    user_rules: Sequence[UserRule] = (),
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
        await _process_card_email(
            db, connection, envelope, message_id, linked, result, user_rules, client
        )
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
    source = parsed.source or parser.name
    twin = await find_manual_twin(db, connection.user_id, source, parsed)
    if twin is not None:
        # The user typed this one in while the email was missing: the email
        # backs that row now instead of becoming a second copy. The typed
        # date stays, so the reconciliation that absorbed it still holds.
        twin.provider_connection_id = connection.id
        twin.raw_email_reference = parsed.raw_email_reference or message_id
        await db.flush()
        result.skipped_duplicate += 1
        return
    try:
        async with db.begin_nested():
            tx = _to_transaction(
                parsed,
                connection,
                fallback_message_id=message_id,
                source=source,
                user_rules=user_rules,
            )
            db.add(tx)
            if source == CASH_SOURCE:
                # A cash expense dated before the last cash count is already
                # inside it — same rule as the ones the user types in.
                await keep_cash_reconciled(
                    db, connection.user_id, None, (tx.amount, tx.occurred_at)
                )
            await db.flush()
    except IntegrityError:
        result.skipped_duplicate += 1
        return
    result.created += 1


# A bank email that shows up late (or the user typed it in first) lands within
# a few days of the date the user picked.
MANUAL_TWIN_WINDOW = timedelta(days=3)
_MANUAL_BANK_SOURCES = ("davivienda", "nequi")


async def find_manual_twin(
    db: AsyncSession, user_id, source: str, parsed: ParsedTransaction
) -> Transaction | None:
    """A typed-in row of the same account, direction and amount near the
    email's date, not yet backed by any email — the closest one."""
    if source not in _MANUAL_BANK_SOURCES:
        return None
    candidates = (
        (
            await db.execute(
                select(Transaction).where(
                    Transaction.user_id == user_id,
                    Transaction.source == source,
                    Transaction.provider_connection_id.is_(None),
                    Transaction.raw_email_reference.is_(None),
                    Transaction.transaction_type == parsed.transaction_type,
                    Transaction.amount == parsed.amount,
                    Transaction.occurred_at >= parsed.occurred_at - MANUAL_TWIN_WINDOW,
                    Transaction.occurred_at <= parsed.occurred_at + MANUAL_TWIN_WINDOW,
                )
            )
        )
        .scalars()
        .all()
    )
    if not candidates:
        return None
    return min(candidates, key=lambda t: abs(t.occurred_at - parsed.occurred_at))


async def _process_card_email(
    db: AsyncSession,
    connection: ProviderConnection,
    envelope: EmailEnvelope,
    message_id: str,
    linked: list[Debt],
    result: SyncResult,
    user_rules: Sequence[UserRule] = (),
    client: GmailClient | None = None,
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
            # Until the PDF is read: the email's arrival stands in for the cut-off.
            debt.statement_at = event.occurred_at
            debt.next_installments = None
            if client is not None:
                await _apply_statement_pdf(
                    db, client, connection, debt, envelope, message_id, user_rules
                )
        result.card_statements += 1
        return

    tx = card_event_to_transaction(event, debt, connection, message_id, user_rules)
    try:
        async with db.begin_nested():
            db.add(tx)
            await db.flush()
    except IntegrityError:
        result.skipped_duplicate += 1
        return
    apply_card_event_to_balance(debt, event)
    result.created += 1


async def _apply_statement_pdf(
    db: AsyncSession,
    client: GmailClient,
    connection: ProviderConnection,
    debt: Debt,
    envelope: EmailEnvelope,
    message_id: str,
    user_rules: Sequence[UserRule],
) -> None:
    """Read the statement PDF attached to the email (cut-off, installments,
    missed purchases, balance). Best effort: without the PDF or its password
    the email's minimum and due date are still applied."""
    if debt.email_format != "rappicard" or not envelope.attachments:
        return
    attachment = next(
        (a for a in envelope.attachments if "statement" in a.filename.lower()),
        envelope.attachments[0],
    )
    try:
        pdf_bytes = await asyncio.to_thread(
            client.get_attachment, message_id, attachment.attachment_id
        )
        statement = await asyncio.to_thread(
            extract_statement, pdf_bytes, _statement_pdf_password()
        )
    except Exception:  # noqa: BLE001 — wrong/missing password, not a PDF, layout change
        log.warning("gmail_sync card_statement_pdf_unreadable message_id=%s", message_id)
        return
    if statement is None:
        log.warning("gmail_sync card_statement_pdf_no_period message_id=%s", message_id)
        return
    await apply_card_statement(db, connection, debt, statement, user_rules)


def _statement_pdf_password() -> str:
    """Davivienda issues the card and locks its PDFs like Itaú's statements
    (the holder's ID): one configured password opens both."""
    return settings.rappicard_statement_pdf_password or settings.itau_statement_pdf_password


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
    user_rules: Sequence[UserRule] = (),
) -> Transaction:
    if event.kind is CardEventKind.purchase:
        # Real spending, counted the day it happens; categorized like any purchase.
        return Transaction(
            user_id=connection.user_id,
            provider_connection_id=connection.id,
            amount=event.amount,
            merchant=event.merchant,
            category=categorize(event.merchant, user_rules),
            transaction_type=TransactionType.debit,
            currency="COP",
            card_last_digits=event.card_last_digits,
            occurred_at=event.occurred_at,
            raw_email_reference=message_id,
            debt_id=debt.id,
            source="card",
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
        source="card",
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
    source: str | None = None,
    user_rules: Sequence[UserRule] = (),
) -> Transaction:
    # Parser decisions (transfer, cash_withdrawal…) win over any rule.
    category = (
        parsed.category
        if parsed.category is not None
        else categorize(parsed.merchant, user_rules)
    )
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
        source=source,
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
