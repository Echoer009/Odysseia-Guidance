"""Create initial tables with pg_search and HNSW

Revision ID: 578adbc7c4bd
Revises:
Create Date: 2025-12-18 12:41:47.299105

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "578adbc7c4bd"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Phase 1: Only install the required extensions.
    This is to ensure they are fully available before being used in a subsequent migration.
    """
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_search;")


def downgrade() -> None:
    """
    Phase 1 Downgrade: Remove the extensions.
    """
    op.execute("DROP EXTENSION IF EXISTS pg_search;")
    op.execute("DROP EXTENSION IF EXISTS vector;")
