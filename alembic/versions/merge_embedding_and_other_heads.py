"""merge embedding dimension update with other heads

Revision ID: merge_heads_20260308
Revises: (update_dim_1024, d4d2d70d3faa)
Create Date: 2026-03-08

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "merge_heads_20260308"
down_revision: Union[str, Sequence[str], None] = ("update_dim_1024", "d4d2d70d3faa")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge branches - no schema changes needed"""
    pass


def downgrade() -> None:
    """Unmerge branches - no schema changes needed"""
    pass
