"""shared expenses: transactions.shared_amount

Revision ID: c3e1f5a7b9d2
Revises: b8d4f0a2c3e5
Create Date: 2026-11-07 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3e1f5a7b9d2'
down_revision: Union[str, Sequence[str], None] = 'b8d4f0a2c3e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'transactions',
        sa.Column('shared_amount', sa.Numeric(precision=12, scale=2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('transactions', 'shared_amount')
