"""shared bills: planned payments every N months, variable amount, shared part

Revision ID: d4f2a6b8c0e1
Revises: c3e1f5a7b9d2
Create Date: 2026-11-07 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4f2a6b8c0e1'
down_revision: Union[str, Sequence[str], None] = 'c3e1f5a7b9d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'planned_payments',
        sa.Column('every_months', sa.Integer(), server_default='1', nullable=False),
    )
    op.add_column('planned_payments', sa.Column('first_month', sa.String(length=7), nullable=True))
    op.add_column(
        'planned_payments',
        sa.Column('amount_varies', sa.Boolean(), server_default='false', nullable=False),
    )
    op.add_column('planned_payments', sa.Column('shared_pct', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('planned_payments', 'shared_pct')
    op.drop_column('planned_payments', 'amount_varies')
    op.drop_column('planned_payments', 'first_month')
    op.drop_column('planned_payments', 'every_months')
