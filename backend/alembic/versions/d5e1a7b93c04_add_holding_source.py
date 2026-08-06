"""add holding source

Splits ownership of `holdings`: positions in a linked brokerage are replaced
from Plaid on every sync, while anything Plaid cannot see stays 'manual'.
Existing rows are manual by definition — they were all typed in.

Revision ID: d5e1a7b93c04
Revises: c8b204de77a1
Create Date: 2026-08-05 23:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5e1a7b93c04'
down_revision: Union[str, Sequence[str], None] = 'c8b204de77a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'holdings',
        sa.Column('source', sa.String(length=16), nullable=False, server_default='manual'),
    )
    op.alter_column('holdings', 'source', server_default=None)
    op.add_column('holdings', sa.Column('plaid_security_id', sa.String(length=64), nullable=True))
    op.create_index('ix_holdings_plaid_security_id', 'holdings', ['plaid_security_id'])
    op.create_check_constraint('ck_holding_source', 'holdings', "source IN ('manual', 'plaid')")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_holding_source', 'holdings', type_='check')
    op.drop_index('ix_holdings_plaid_security_id', table_name='holdings')
    op.drop_column('holdings', 'plaid_security_id')
    op.drop_column('holdings', 'source')
