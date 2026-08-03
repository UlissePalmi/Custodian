"""add plaid sync

Revision ID: f4a1c9d02b7e
Revises: b31edd4ea603
Create Date: 2026-08-02 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4a1c9d02b7e'
down_revision: Union[str, Sequence[str], None] = 'b31edd4ea603'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'plaid_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('item_id', sa.String(length=64), nullable=False),
        sa.Column('access_token_encrypted', sa.String(length=500), nullable=False),
        sa.Column('institution_name', sa.String(length=120), nullable=False),
        sa.Column('cursor', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.String(length=500), nullable=True),
        sa.CheckConstraint("status IN ('active', 'error', 'disconnected')", name='ck_plaid_item_status'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_plaid_items_item_id'), 'plaid_items', ['item_id'], unique=True)

    op.create_table(
        'plaid_category_map',
        sa.Column('plaid_category', sa.String(length=64), nullable=False),
        sa.Column('category_id', sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id']),
        sa.PrimaryKeyConstraint('plaid_category'),
    )

    op.add_column('transactions', sa.Column('plaid_transaction_id', sa.String(length=64), nullable=True))
    op.create_index(
        op.f('ix_transactions_plaid_transaction_id'),
        'transactions',
        ['plaid_transaction_id'],
        unique=True,
    )
    op.drop_constraint('ck_transaction_source', 'transactions', type_='check')
    op.create_check_constraint(
        'ck_transaction_source', 'transactions', "source IN ('manual', 'chase_import', 'plaid')"
    )

    op.add_column(
        'import_batches',
        sa.Column('source', sa.String(length=16), nullable=False, server_default='chase_import'),
    )
    op.alter_column('import_batches', 'source', server_default=None)
    op.add_column('import_batches', sa.Column('plaid_item_id', sa.String(length=64), nullable=True))
    op.create_foreign_key(
        'fk_import_batches_plaid_item_id',
        'import_batches',
        'plaid_items',
        ['plaid_item_id'],
        ['item_id'],
        ondelete='SET NULL',
    )
    op.create_check_constraint(
        'ck_import_batch_source', 'import_batches', "source IN ('chase_import', 'plaid')"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_import_batch_source', 'import_batches', type_='check')
    op.drop_constraint('fk_import_batches_plaid_item_id', 'import_batches', type_='foreignkey')
    op.drop_column('import_batches', 'plaid_item_id')
    op.drop_column('import_batches', 'source')

    op.drop_constraint('ck_transaction_source', 'transactions', type_='check')
    op.create_check_constraint(
        'ck_transaction_source', 'transactions', "source IN ('manual', 'chase_import')"
    )
    op.drop_index(op.f('ix_transactions_plaid_transaction_id'), table_name='transactions')
    op.drop_column('transactions', 'plaid_transaction_id')

    op.drop_table('plaid_category_map')

    op.drop_index(op.f('ix_plaid_items_item_id'), table_name='plaid_items')
    op.drop_table('plaid_items')
