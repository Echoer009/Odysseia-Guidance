"""merge_heads

Revision ID: d1b5ce4c26a4
Revises: 40a238a8bfb3, add_shop_items
Create Date: 2026-02-09 14:37:59.889637

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1b5ce4c26a4'
down_revision: Union[str, Sequence[str], None] = ('40a238a8bfb3', 'add_shop_items')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
