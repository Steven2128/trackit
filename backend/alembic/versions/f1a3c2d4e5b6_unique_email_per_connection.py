"""unique email per connection

Partial unique index on (provider_connection_id, raw_email_reference) to
guard against duplicate transactions when the sync re-fetches an email
already stored. The app-level dedupe in services/email_sync.py is the first
line of defense; this index is the belt.

Revision ID: f1a3c2d4e5b6
Revises: bb7d501f612c
Create Date: 2026-05-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "f1a3c2d4e5b6"
down_revision: Union[str, Sequence[str], None] = "bb7d501f612c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


INDEX_NAME = "ix_transactions_provider_email_uniq"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE UNIQUE INDEX {INDEX_NAME}
        ON transactions (provider_connection_id, raw_email_reference)
        WHERE raw_email_reference IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
