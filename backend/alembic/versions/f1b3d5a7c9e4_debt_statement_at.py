"""debts: statement_at (when the last card statement email arrived), next_installments

Revision ID: f1b3d5a7c9e4
Revises: c9e1f3a5b7d2
Create Date: 2026-11-12 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1b3d5a7c9e4'
down_revision: Union[str, Sequence[str], None] = 'c9e1f3a5b7d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('debts', sa.Column('statement_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('debts', sa.Column('next_installments', sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    op.drop_column('debts', 'next_installments')
    op.drop_column('debts', 'statement_at')
