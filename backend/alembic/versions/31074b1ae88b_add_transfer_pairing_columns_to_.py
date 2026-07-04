"""add transfer pairing columns to transactions

Revision ID: 31074b1ae88b
Revises: f1a3c2d4e5b6
Create Date: 2026-07-04 00:19:58.082181

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '31074b1ae88b'
down_revision: Union[str, Sequence[str], None] = 'f1a3c2d4e5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('transactions', sa.Column('is_pairing_candidate', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('transactions', sa.Column('transfer_pair_id', sa.UUID(), nullable=True))
    op.create_index('ix_transactions_pairing_candidate', 'transactions', ['user_id', 'is_pairing_candidate', 'occurred_at'], unique=False, postgresql_where=sa.text('is_pairing_candidate IS TRUE AND transfer_pair_id IS NULL'))
    op.create_index(op.f('ix_transactions_transfer_pair_id'), 'transactions', ['transfer_pair_id'], unique=False)

    # Backfill: debits already synced before this migration that the matcher
    # should consider (Itaú "Débito · Canal: Portal Internet").
    op.execute(
        """
        UPDATE transactions
        SET is_pairing_candidate = TRUE
        WHERE transaction_type = 'debit'
          AND merchant = 'Portal Internet'
          AND category IS DISTINCT FROM 'transfer'
        """
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_transactions_transfer_pair_id'), table_name='transactions')
    op.drop_index('ix_transactions_pairing_candidate', table_name='transactions', postgresql_where=sa.text('is_pairing_candidate IS TRUE AND transfer_pair_id IS NULL'))
    op.drop_column('transactions', 'transfer_pair_id')
    op.drop_column('transactions', 'is_pairing_candidate')
