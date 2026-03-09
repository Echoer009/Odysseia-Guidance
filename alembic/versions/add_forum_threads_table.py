"""add_forum_threads_table

Revision ID: add_forum_threads
Revises: merge_heads_20260308
Create Date: 2026-03-09 08:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = "add_forum_threads"
down_revision: Union[str, Sequence[str], None] = "merge_heads_20260308"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create forum schema
    op.execute(text("CREATE SCHEMA IF NOT EXISTS forum"))

    # Create forum_threads table
    op.execute(
        text("""
        CREATE TABLE forum.forum_threads (
            id SERIAL NOT NULL,
            thread_id BIGINT NOT NULL UNIQUE,
            thread_name TEXT NOT NULL,
            content TEXT NOT NULL,
            author_id BIGINT NOT NULL,
            author_name TEXT NOT NULL,
            category_name TEXT NOT NULL,
            channel_id BIGINT NOT NULL,
            guild_id BIGINT NOT NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            source_metadata JSONB,
            embedding HALFVEC(1024),
            created_at_db TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
            PRIMARY KEY (id)
        )
    """)
    )

    # Create indexes
    # Primary key index (automatically created)

    # HNSW vector index for similarity search
    op.execute(
        text("""
        CREATE INDEX idx_forum_embedding_hnsw
        ON forum.forum_threads
        USING hnsw (embedding halfvec_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    )

    # BM25 full-text search index
    op.execute(
        text("""
        CREATE INDEX idx_forum_threads_bm25
        ON forum.forum_threads
        USING bm25 (id, ((content)::pdb.chinese_compatible))
        WITH (key_field=id)
    """)
    )

    # Created at index for sorting
    op.execute(
        text("""
        CREATE INDEX idx_forum_created_at
        ON forum.forum_threads (created_at)
    """)
    )

    # Category name index for filtering
    op.execute(
        text("""
        CREATE INDEX idx_forum_category
        ON forum.forum_threads (category_name)
    """)
    )

    # Author ID index for filtering
    op.execute(
        text("""
        CREATE INDEX idx_forum_author
        ON forum.forum_threads (author_id)
    """)
    )

    # Channel ID index for filtering
    op.execute(
        text("""
        CREATE INDEX idx_forum_channel
        ON forum.forum_threads (channel_id)
    """)
    )

    # Add comments to table and columns
    op.execute(
        text("""
        COMMENT ON TABLE forum.forum_threads IS '论坛帖子表，用于语义搜索和全文搜索'
    """)
    )
    op.execute(
        text("""
        COMMENT ON COLUMN forum.forum_threads.thread_id IS 'Discord帖子的唯一ID'
    """)
    )
    op.execute(
        text("""
        COMMENT ON COLUMN forum.forum_threads.thread_name IS '帖子标题'
    """)
    )
    op.execute(
        text("""
        COMMENT ON COLUMN forum.forum_threads.content IS '帖子完整内容（首楼）'
    """)
    )
    op.execute(
        text("""
        COMMENT ON COLUMN forum.forum_threads.author_id IS '作者的Discord ID'
    """)
    )
    op.execute(
        text("""
        COMMENT ON COLUMN forum.forum_threads.author_name IS '作者的显示名称'
    """)
    )
    op.execute(
        text("""
        COMMENT ON COLUMN forum.forum_threads.category_name IS '论坛频道名称（分类）'
    """)
    )
    op.execute(
        text("""
        COMMENT ON COLUMN forum.forum_threads.channel_id IS '父频道的Discord ID'
    """)
    )
    op.execute(
        text("""
        COMMENT ON COLUMN forum.forum_threads.guild_id IS '服务器的Discord ID'
    """)
    )
    op.execute(
        text("""
        COMMENT ON COLUMN forum.forum_threads.created_at IS '帖子创建时间（Discord时间）'
    """)
    )
    op.execute(
        text("""
        COMMENT ON COLUMN forum.forum_threads.source_metadata IS '来自旧系统的完整元数据备份'
    """)
    )
    op.execute(
        text("""
        COMMENT ON COLUMN forum.forum_threads.embedding IS '整帖内容的向量嵌入（用于语义搜索）'
    """)
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop all indexes
    op.execute(text("DROP INDEX IF EXISTS forum.idx_forum_embedding_hnsw"))
    op.execute(text("DROP INDEX IF EXISTS forum.idx_forum_threads_bm25"))
    op.execute(text("DROP INDEX IF EXISTS forum.idx_forum_created_at"))
    op.execute(text("DROP INDEX IF EXISTS forum.idx_forum_category"))
    op.execute(text("DROP INDEX IF EXISTS forum.idx_forum_author"))
    op.execute(text("DROP INDEX IF EXISTS forum.idx_forum_channel"))

    # Drop table
    op.execute(text("DROP TABLE IF EXISTS forum.forum_threads"))

    # Drop schema
    op.execute(text("DROP SCHEMA IF EXISTS forum"))
