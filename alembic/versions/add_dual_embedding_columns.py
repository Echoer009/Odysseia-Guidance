"""add dual embedding columns (bge_embedding, qwen_embedding)

Revision ID: add_dual_embedding
Revises: fix_forum_threads_bigint
Create Date: 2026-03-11

将现有的 embedding 列重命名为 bge_embedding，
并添加新的 qwen_embedding 列用于双 embedding 支持。

涉及的表：
- tutorials.knowledge_chunks
- general_knowledge.knowledge_chunks
- community.member_chunks
- forum.forum_threads

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "add_dual_embedding"
down_revision: Union[str, Sequence[str], None] = "fix_forum_threads_bigint"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - 添加双 embedding 列支持"""

    # =====================================================
    # 1. tutorials.knowledge_chunks
    # =====================================================
    # 删除旧的 HNSW 索引
    op.execute("DROP INDEX IF EXISTS tutorials.idx_embedding_hnsw")

    # 重命名 embedding -> bge_embedding
    op.execute(
        "ALTER TABLE tutorials.knowledge_chunks RENAME COLUMN embedding TO bge_embedding"
    )

    # 添加 qwen_embedding 列
    op.execute(
        "ALTER TABLE tutorials.knowledge_chunks ADD COLUMN qwen_embedding halfvec(1024)"
    )

    # 创建新的 HNSW 索引
    op.execute("""
        CREATE INDEX idx_bge_embedding_hnsw
        ON tutorials.knowledge_chunks
        USING hnsw (bge_embedding halfvec_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    op.execute("""
        CREATE INDEX idx_qwen_embedding_hnsw
        ON tutorials.knowledge_chunks
        USING hnsw (qwen_embedding halfvec_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # =====================================================
    # 2. general_knowledge.knowledge_chunks
    # =====================================================
    # 删除旧的 HNSW 索引
    op.execute("DROP INDEX IF EXISTS general_knowledge.idx_gk_embedding_hnsw")

    # 重命名 embedding -> bge_embedding
    op.execute(
        "ALTER TABLE general_knowledge.knowledge_chunks RENAME COLUMN embedding TO bge_embedding"
    )

    # 添加 qwen_embedding 列
    op.execute(
        "ALTER TABLE general_knowledge.knowledge_chunks ADD COLUMN qwen_embedding halfvec(1024)"
    )

    # 创建新的 HNSW 索引
    op.execute("""
        CREATE INDEX idx_gk_bge_embedding_hnsw
        ON general_knowledge.knowledge_chunks
        USING hnsw (bge_embedding halfvec_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    op.execute("""
        CREATE INDEX idx_gk_qwen_embedding_hnsw
        ON general_knowledge.knowledge_chunks
        USING hnsw (qwen_embedding halfvec_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # =====================================================
    # 3. community.member_chunks
    # =====================================================
    # 删除旧的 HNSW 索引
    op.execute("DROP INDEX IF EXISTS community.idx_cm_embedding_hnsw")

    # 重命名 embedding -> bge_embedding
    op.execute(
        "ALTER TABLE community.member_chunks RENAME COLUMN embedding TO bge_embedding"
    )

    # 添加 qwen_embedding 列
    op.execute(
        "ALTER TABLE community.member_chunks ADD COLUMN qwen_embedding halfvec(1024)"
    )

    # 创建新的 HNSW 索引
    op.execute("""
        CREATE INDEX idx_cm_bge_embedding_hnsw
        ON community.member_chunks
        USING hnsw (bge_embedding halfvec_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    op.execute("""
        CREATE INDEX idx_cm_qwen_embedding_hnsw
        ON community.member_chunks
        USING hnsw (qwen_embedding halfvec_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # =====================================================
    # 4. forum.forum_threads
    # =====================================================
    # 删除旧的 HNSW 索引（如果存在）
    op.execute("DROP INDEX IF EXISTS forum.idx_forum_embedding_hnsw")

    # 重命名 embedding -> bge_embedding（如果存在 embedding 列）
    # 注意：forum_threads 表可能已经有 bge_embedding 列或者有 embedding 列
    # 需要先检查列是否存在
    op.execute("""
        DO $$
        BEGIN
            -- 如果 embedding 列存在且 bge_embedding 列不存在，则重命名
            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_schema = 'forum' 
                AND table_name = 'forum_threads' 
                AND column_name = 'embedding'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_schema = 'forum' 
                AND table_name = 'forum_threads' 
                AND column_name = 'bge_embedding'
            ) THEN
                ALTER TABLE forum.forum_threads RENAME COLUMN embedding TO bge_embedding;
            END IF;
        END $$;
    """)

    # 添加 bge_embedding 列（如果不存在）
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_schema = 'forum' 
                AND table_name = 'forum_threads' 
                AND column_name = 'bge_embedding'
            ) THEN
                ALTER TABLE forum.forum_threads ADD COLUMN bge_embedding halfvec(1024);
            END IF;
        END $$;
    """)

    # 添加 qwen_embedding 列（如果不存在）
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_schema = 'forum' 
                AND table_name = 'forum_threads' 
                AND column_name = 'qwen_embedding'
            ) THEN
                ALTER TABLE forum.forum_threads ADD COLUMN qwen_embedding halfvec(1024);
            END IF;
        END $$;
    """)

    # 创建新的 HNSW 索引
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_forum_bge_embedding_hnsw
        ON forum.forum_threads
        USING hnsw (bge_embedding halfvec_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_forum_qwen_embedding_hnsw
        ON forum.forum_threads
        USING hnsw (qwen_embedding halfvec_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)


def downgrade() -> None:
    """Downgrade schema - 回滚到单一 embedding 列"""

    # =====================================================
    # 1. tutorials.knowledge_chunks
    # =====================================================
    # 删除新的 HNSW 索引
    op.execute("DROP INDEX IF EXISTS tutorials.idx_bge_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS tutorials.idx_qwen_embedding_hnsw")

    # 删除 qwen_embedding 列
    op.execute(
        "ALTER TABLE tutorials.knowledge_chunks DROP COLUMN IF EXISTS qwen_embedding"
    )

    # 重命名 bge_embedding -> embedding
    op.execute(
        "ALTER TABLE tutorials.knowledge_chunks RENAME COLUMN bge_embedding TO embedding"
    )

    # 重新创建旧索引
    op.execute("""
        CREATE INDEX idx_embedding_hnsw
        ON tutorials.knowledge_chunks
        USING hnsw (embedding halfvec_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # =====================================================
    # 2. general_knowledge.knowledge_chunks
    # =====================================================
    op.execute("DROP INDEX IF EXISTS general_knowledge.idx_gk_bge_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS general_knowledge.idx_gk_qwen_embedding_hnsw")

    op.execute(
        "ALTER TABLE general_knowledge.knowledge_chunks DROP COLUMN IF EXISTS qwen_embedding"
    )

    op.execute(
        "ALTER TABLE general_knowledge.knowledge_chunks RENAME COLUMN bge_embedding TO embedding"
    )

    op.execute("""
        CREATE INDEX idx_gk_embedding_hnsw
        ON general_knowledge.knowledge_chunks
        USING hnsw (embedding halfvec_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # =====================================================
    # 3. community.member_chunks
    # =====================================================
    op.execute("DROP INDEX IF EXISTS community.idx_cm_bge_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS community.idx_cm_qwen_embedding_hnsw")

    op.execute(
        "ALTER TABLE community.member_chunks DROP COLUMN IF EXISTS qwen_embedding"
    )

    op.execute(
        "ALTER TABLE community.member_chunks RENAME COLUMN bge_embedding TO embedding"
    )

    op.execute("""
        CREATE INDEX idx_cm_embedding_hnsw
        ON community.member_chunks
        USING hnsw (embedding halfvec_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # =====================================================
    # 4. forum.forum_threads
    # =====================================================
    op.execute("DROP INDEX IF EXISTS forum.idx_forum_bge_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS forum.idx_forum_qwen_embedding_hnsw")

    op.execute("ALTER TABLE forum.forum_threads DROP COLUMN IF EXISTS qwen_embedding")

    # 重命名 bge_embedding -> embedding
    op.execute(
        "ALTER TABLE forum.forum_threads RENAME COLUMN bge_embedding TO embedding"
    )

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_forum_embedding_hnsw
        ON forum.forum_threads
        USING hnsw (embedding halfvec_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
