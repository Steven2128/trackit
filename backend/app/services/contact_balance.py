"""Who owes whom with each contact.

The balance is computed from the transactions that name the contact, never
stored, so editing or deleting a movement can't leave it stale. Positive =
the contact owes the user; negative = the user owes the contact.

- A debit the user paid with ``shared_amount`` (their part of the bill)
  → +shared_amount.
- An expense the contact paid (``source="contact"``, a debit that moves no
  account of the user): the user owes their own part → −(amount − shared_amount).
- Money between them, category "reimbursement": a credit (the contact paid
  back or lent) → −amount; a debit (the user paid back or lent) → +amount.

Splitting 50/50 is just the default the app fills in; ``shared_amount`` can be
any part, so "whoever paid more gets the difference" falls out of the sum.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from app.models.transaction import TransactionType

CONTACT_SOURCE = "contact"
REIMBURSEMENT = "reimbursement"
ZERO = Decimal("0")


class _Row(Protocol):
    source: str | None
    transaction_type: TransactionType
    category: str | None
    amount: Decimal
    shared_amount: Decimal | None


def balance_effect(row: _Row) -> Decimal:
    """What one movement adds to "the contact owes the user"."""
    shared = row.shared_amount or ZERO
    if row.category == REIMBURSEMENT:
        return row.amount if row.transaction_type == TransactionType.debit else -row.amount
    if row.transaction_type != TransactionType.debit:
        return ZERO
    if row.source == CONTACT_SOURCE:
        return -(row.amount - shared)
    return shared
