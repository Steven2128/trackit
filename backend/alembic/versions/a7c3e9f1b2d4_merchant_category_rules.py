"""merchant category rules (user rules for the categorizer)

Revision ID: a7c3e9f1b2d4
Revises: 93c95cba230c
Create Date: 2026-10-19 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7c3e9f1b2d4'
down_revision: Union[str, Sequence[str], None] = '93c95cba230c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('merchant_category_rules',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('pattern', sa.String(length=64), nullable=False),
    sa.Column('category', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'pattern', name='uq_merchant_category_rules_user_pattern')
    )
    op.create_index(op.f('ix_merchant_category_rules_user_id'), 'merchant_category_rules', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_merchant_category_rules_user_id'), table_name='merchant_category_rules')
    op.drop_table('merchant_category_rules')
