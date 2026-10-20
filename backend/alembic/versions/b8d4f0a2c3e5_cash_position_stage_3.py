"""cash position stage 3: fund holds, one-off and partial payments, planned debt payment

Revision ID: b8d4f0a2c3e5
Revises: a7c3e9f1b2d4
Create Date: 2026-10-20 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8d4f0a2c3e5'
down_revision: Union[str, Sequence[str], None] = 'a7c3e9f1b2d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('fund_holds',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('amount', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_fund_holds_user_id'), 'fund_holds', ['user_id'], unique=False)

    op.create_table('obligation_payments',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('planned_payment_id', sa.UUID(), nullable=True),
    sa.Column('debt_id', sa.UUID(), nullable=True),
    sa.Column('due_date', sa.Date(), nullable=False),
    sa.Column('amount', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('paid_on', sa.Date(), nullable=False),
    sa.Column('transaction_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('(planned_payment_id IS NULL) <> (debt_id IS NULL)', name='ck_obligation_payments_one_parent'),
    sa.ForeignKeyConstraint(['debt_id'], ['debts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['planned_payment_id'], ['planned_payments.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_obligation_payments_user_id'), 'obligation_payments', ['user_id'], unique=False)
    op.create_index(op.f('ix_obligation_payments_planned_payment_id'), 'obligation_payments', ['planned_payment_id'], unique=False)
    op.create_index(op.f('ix_obligation_payments_debt_id'), 'obligation_payments', ['debt_id'], unique=False)

    op.add_column('planned_payments', sa.Column('due_date', sa.Date(), nullable=True))
    op.add_column('debts', sa.Column('planned_payment', sa.Numeric(precision=12, scale=2), nullable=True))


def downgrade() -> None:
    op.drop_column('debts', 'planned_payment')
    op.drop_column('planned_payments', 'due_date')
    op.drop_index(op.f('ix_obligation_payments_debt_id'), table_name='obligation_payments')
    op.drop_index(op.f('ix_obligation_payments_planned_payment_id'), table_name='obligation_payments')
    op.drop_index(op.f('ix_obligation_payments_user_id'), table_name='obligation_payments')
    op.drop_table('obligation_payments')
    op.drop_index(op.f('ix_fund_holds_user_id'), table_name='fund_holds')
    op.drop_table('fund_holds')
