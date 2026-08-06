"""drop chase import

Removes the Chase file-import feature's table. Plaid syncs the same data
directly, so the parser, its preview/confirm flow and its category mapping are
gone; `import_batches` and the transactions it produced stay, since batches are
now created by syncing and the undo path is unchanged.

`ck_transaction_source` still permits 'chase_import' so any historical row
imported that way remains valid.

Revision ID: c8b204de77a1
Revises: a7c3e91f45d2
Create Date: 2026-08-05 23:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8b204de77a1'
down_revision: Union[str, Sequence[str], None] = 'a7c3e91f45d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_table('chase_category_map')


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table(
        'chase_category_map',
        sa.Column('chase_category', sa.String(length=120), nullable=False),
        sa.Column('category_id', sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id']),
        sa.PrimaryKeyConstraint('chase_category'),
    )
