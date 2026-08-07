"""drop net worth snapshots

Monthly snapshots were written from three places and read from none once the
dashboard chart moved to `daily_net_worth`, which covers the same ground a day
at a time and refills itself after a gap.

Rows are not preserved: they recorded a live total stamped into whichever
month was being written, so they were never a reliable history of those
months, and the daily series already spans the period.

Revision ID: a41f7e9b28c3
Revises: c3d8f52a71b6
Create Date: 2026-08-06 23:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a41f7e9b28c3'
down_revision: Union[str, Sequence[str], None] = 'c3d8f52a71b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_table('net_worth_snapshots')


def downgrade() -> None:
    """Downgrade schema. Recreates the table empty — the rows are gone."""
    op.create_table(
        'net_worth_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('month_key', sa.String(length=7), nullable=False),
        sa.Column('as_of', sa.Date(), nullable=False),
        sa.Column('total', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('breakdown', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('month_key'),
    )
