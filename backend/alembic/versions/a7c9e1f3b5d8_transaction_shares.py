"""transaction_shares: split one debit among several contacts

Revision ID: a7c9e1f3b5d8
Revises: c4e6a8b0d2f3
Create Date: 2026-11-25 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a7c9e1f3b5d8'
down_revision: Union[str, Sequence[str], None] = 'c4e6a8b0d2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'transaction_shares',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('transaction_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('contact_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False
        ),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['contact_id'], ['contacts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('transaction_id', 'contact_id', name='uq_transaction_shares_tx_contact'),
    )
    op.create_index(
        op.f('ix_transaction_shares_transaction_id'), 'transaction_shares', ['transaction_id']
    )
    op.create_index(op.f('ix_transaction_shares_contact_id'), 'transaction_shares', ['contact_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_transaction_shares_contact_id'), table_name='transaction_shares')
    op.drop_index(op.f('ix_transaction_shares_transaction_id'), table_name='transaction_shares')
    op.drop_table('transaction_shares')
