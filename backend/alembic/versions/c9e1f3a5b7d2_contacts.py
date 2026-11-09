"""contacts + transactions.contact_id (who a shared expense or payback is with)

Revision ID: c9e1f3a5b7d2
Revises: e5a3b7c9d1f2
Create Date: 2026-11-09 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c9e1f3a5b7d2'
down_revision: Union[str, Sequence[str], None] = 'e5a3b7c9d1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'contacts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'name', name='uq_contacts_user_name'),
    )
    op.create_index(op.f('ix_contacts_user_id'), 'contacts', ['user_id'], unique=False)
    op.add_column(
        'transactions', sa.Column('contact_id', postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_index(
        op.f('ix_transactions_contact_id'), 'transactions', ['contact_id'], unique=False
    )
    op.create_foreign_key(
        'fk_transactions_contact_id_contacts', 'transactions', 'contacts',
        ['contact_id'], ['id'], ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_transactions_contact_id_contacts', 'transactions', type_='foreignkey')
    op.drop_index(op.f('ix_transactions_contact_id'), table_name='transactions')
    op.drop_column('transactions', 'contact_id')
    op.drop_index(op.f('ix_contacts_user_id'), table_name='contacts')
    op.drop_table('contacts')
