"""add balance checkpoints

Per-account drift became structurally impossible once a mapped balance was
taken from the bank. This replaces it with a check that still means something:
whether the ledger saw everything that moved, tracked over time rather than at
a moment.

Revision ID: f9c027ab4e15
Revises: e2f4b81c60a9
Create Date: 2026-08-06 00:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f9c027ab4e15'
down_revision: Union[str, Sequence[str], None] = 'e2f4b81c60a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'balance_checkpoints',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('taken_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tracked_total', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('ledger_net', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_balance_checkpoints_taken_at'), 'balance_checkpoints', ['taken_at'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_balance_checkpoints_taken_at'), table_name='balance_checkpoints')
    op.drop_table('balance_checkpoints')
