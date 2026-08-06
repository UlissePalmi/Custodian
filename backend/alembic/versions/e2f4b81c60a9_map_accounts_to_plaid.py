"""map accounts to plaid

Binds Custodian accounts to real bank accounts and records what the bank
reports alongside the ledger's own running balance. Both are kept: a gap
between them is the signal that a transaction was missed or double-counted,
which is exactly what neither balance can tell you on its own.

Revision ID: e2f4b81c60a9
Revises: d5e1a7b93c04
Create Date: 2026-08-06 00:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2f4b81c60a9'
down_revision: Union[str, Sequence[str], None] = 'd5e1a7b93c04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('accounts', sa.Column('plaid_account_id', sa.String(length=64), nullable=True))
    op.add_column('accounts', sa.Column('plaid_balance', sa.Numeric(precision=14, scale=2), nullable=True))
    op.add_column(
        'accounts',
        sa.Column('plaid_balance_as_of', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint('uq_accounts_plaid_account_id', 'accounts', ['plaid_account_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_accounts_plaid_account_id', 'accounts', type_='unique')
    op.drop_column('accounts', 'plaid_balance_as_of')
    op.drop_column('accounts', 'plaid_balance')
    op.drop_column('accounts', 'plaid_account_id')
