"""income sources: early_from_day (a deposit can come from that day of the previous month)

Revision ID: e5a3b7c9d1f2
Revises: d4f2a6b8c0e1
Create Date: 2026-11-07 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5a3b7c9d1f2'
down_revision: Union[str, Sequence[str], None] = 'd4f2a6b8c0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('income_sources', sa.Column('early_from_day', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('income_sources', 'early_from_day')
