"""add daily net worth

One row per day, so net worth can be seen moving rather than only sampled
monthly. Reconstructed and measured days are stored identically.

Revision ID: c3d8f52a71b6
Revises: f9c027ab4e15
Create Date: 2026-08-06 01:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c3d8f52a71b6'
down_revision: Union[str, Sequence[str], None] = 'f9c027ab4e15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'daily_net_worth',
        sa.Column('day', sa.Date(), nullable=False),
        sa.Column('total', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('breakdown', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint('day'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('daily_net_worth')
