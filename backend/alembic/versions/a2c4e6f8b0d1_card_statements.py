"""card statements read from the PDF: header + movements

Revision ID: a2c4e6f8b0d1
Revises: f1b3d5a7c9e4
Create Date: 2026-11-13 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a2c4e6f8b0d1'
down_revision: Union[str, Sequence[str], None] = 'f1b3d5a7c9e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'card_statements',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('debt_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=True),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('minimum_payment', sa.Numeric(14, 2), nullable=True),
        sa.Column('total_payment', sa.Numeric(14, 2), nullable=True),
        sa.Column('credit_limit', sa.Numeric(14, 2), nullable=True),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['debt_id'], ['debts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('debt_id', 'period_end', name='uq_card_statements_debt_period_end'),
    )
    op.create_index(op.f('ix_card_statements_user_id'), 'card_statements', ['user_id'], unique=False)
    op.create_index(op.f('ix_card_statements_debt_id'), 'card_statements', ['debt_id'], unique=False)
    op.create_table(
        'card_statement_lines',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('statement_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('posted_on', sa.Date(), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=False),
        sa.Column('amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('billed', sa.Numeric(14, 2), nullable=True),
        sa.Column('installment', sa.Integer(), nullable=True),
        sa.Column('installments', sa.Integer(), nullable=True),
        sa.Column('pending', sa.Numeric(14, 2), nullable=True),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False
        ),
        sa.ForeignKeyConstraint(['statement_id'], ['card_statements.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_card_statement_lines_statement_id'), 'card_statement_lines', ['statement_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_card_statement_lines_statement_id'), table_name='card_statement_lines')
    op.drop_table('card_statement_lines')
    op.drop_index(op.f('ix_card_statements_debt_id'), table_name='card_statements')
    op.drop_index(op.f('ix_card_statements_user_id'), table_name='card_statements')
    op.drop_table('card_statements')
