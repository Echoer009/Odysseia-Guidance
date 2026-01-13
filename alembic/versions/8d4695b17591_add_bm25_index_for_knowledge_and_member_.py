"""add_bm25_index_for_knowledge_and_member_chunks

Revision ID: 8d4695b17591
Revises: 8aaf3d1582e2
Create Date: 2026-01-11 09:16:37.193494

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8d4695b17591"
down_revision: Union[str, Sequence[str], None] = "8aaf3d1582e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Manually added commands to create BM25 indexes
    op.execute("""
        CREATE INDEX idx_gk_chunks_bm25
        ON general_knowledge.knowledge_chunks
        USING bm25 (id, ((chunk_text)::pdb.chinese_compatible))
        WITH (key_field=id);
    """)
    op.execute("""
        CREATE INDEX idx_cm_chunks_bm25
        ON community.member_chunks
        USING bm25 (id, ((chunk_text)::pdb.chinese_compatible))
        WITH (key_field=id);
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # Manually added commands to drop BM25 indexes
    op.execute("DROP INDEX IF EXISTS general_knowledge.idx_gk_chunks_bm25;")
    op.execute("DROP INDEX IF EXISTS community.idx_cm_chunks_bm25;")
