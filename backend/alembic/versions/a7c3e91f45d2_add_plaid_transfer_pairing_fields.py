"""add plaid transfer pairing fields

Revision ID: a7c3e91f45d2
Revises: f4a1c9d02b7e
Create Date: 2026-08-05 23:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7c3e91f45d2'
down_revision: Union[str, Sequence[str], None] = 'f4a1c9d02b7e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('transactions', sa.Column('plaid_category', sa.String(length=48), nullable=True))
    op.add_column('transactions', sa.Column('plaid_account_id', sa.String(length=64), nullable=True))
    # Looked up on every sync to find the other half of a transfer.
    op.create_index(
        'ix_transactions_plaid_transfer_lookup',
        'transactions',
        ['plaid_category', 'date'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_transactions_plaid_transfer_lookup', table_name='transactions')
    op.drop_column('transactions', 'plaid_account_id')
    op.drop_column('transactions', 'plaid_category')
